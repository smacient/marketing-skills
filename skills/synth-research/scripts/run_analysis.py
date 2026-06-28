import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import argparse
import csv
import json
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import polars as pl
from semantic_similarity_rating import ResponseRater

from persona_generator import get_personas
from reference_sentences import get_reference_data
from report_generator import generate_report


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

def _gemini_client(model):
    from google import genai
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found. "
            "Set it in ~/.claude/settings.json under 'env' or create a .env file."
        )
    return genai.Client(api_key=api_key), model


def _generate_responses(client, model, personas, stimulus):
    from google import genai
    responses = []
    total = len(personas)
    for i, persona_prompt in enumerate(personas, 1):
        print(f"  Persona {i}/{total}...", end="\r")
        full_prompt = (
            f"{persona_prompt}\n\n"
            f"---\n\n"
            f"CONTENT TO EVALUATE:\n{stimulus}\n\n"
            f"---\n\n"
            f"Your response:"
        )
        resp = client.models.generate_content(model=model, contents=full_prompt)
        responses.append(resp.text.strip())
    print(f"  {total}/{total} persona responses collected.       ")
    return responses


# ---------------------------------------------------------------------------
# SSR
# ---------------------------------------------------------------------------

def _build_rater(reference_data):
    rows = []
    for dim_id, sentences in reference_data.items():
        for i, sentence in enumerate(sentences, 1):
            rows.append({"reference_set_id": dim_id, "text": sentence, "rating": i})
    return ResponseRater(pl.DataFrame(rows))


def _run_ssr(rater, responses, dimensions):
    stats = rater.compute_response_similarities(responses)
    results = {}
    for dim_id in dimensions:
        pmfs = rater.pmfs_from_similarities(dim_id, stats, temp=1.0, eps=0.0)
        agg = rater.get_survey_response_pmf(pmfs)
        expected = round(sum((i + 1) * p for i, p in enumerate(agg)), 2)
        results[dim_id] = {
            "pmf": list(agg),
            "expected": expected,
            "individual_pmfs": [list(p) for p in pmfs],
        }
    return results


def _run_for_stimulus(label, stimulus, personas, rater, dimensions, client, model):
    print(f"\n[{label}] Generating {len(personas)} persona responses...")
    responses = _generate_responses(client, model, personas, stimulus)
    print(f"[{label}] Running SSR...")
    results = _run_ssr(rater, responses, dimensions)
    return results, responses


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _save_pmf_csv(all_results, output_dir, timestamp):
    path = Path(output_dir) / f"{timestamp}-pmf.csv"
    rows = []
    for label, results in all_results.items():
        for dim_id, data in results.items():
            row = {
                "label": label,
                "dimension": dim_id,
                "expected_value": data["expected"],
            }
            for i, p in enumerate(data["pmf"], 1):
                row[f"p{i}"] = round(p, 4)
            rows.append(row)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"PMF data: {path}")


def _save_responses_csv(all_responses, output_dir, timestamp):
    path = Path(output_dir) / f"{timestamp}-responses.csv"
    rows = []
    for label, (responses, results) in all_responses.items():
        for i, response in enumerate(responses):
            row = {"label": label, "persona_index": i, "response": response}
            for dim_id, data in results.items():
                if i < len(data["individual_pmfs"]):
                    pmf = data["individual_pmfs"][i]
                    row[f"{dim_id}_score"] = round(
                        sum((j + 1) * p for j, p in enumerate(pmf)), 2
                    )
            rows.append(row)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Responses: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to JSON config file")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    timestamp = config.get("timestamp", "run")
    mode = config["mode"]
    stimulus = config["stimulus"]
    competitor = config.get("competitor_stimulus")
    audience_config = config["audience"]
    dimensions = config["dimensions"]
    persona_count = config.get("persona_count")
    model_name = config.get("llm_model", "gemini-2.5-flash")
    output_dir = config.get("output_dir", "outputs")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print(f"\nsynth-research v1")
    print(f"Mode: {mode} | Dimensions: {len(dimensions)} | Personas: {persona_count or 'default'}")
    print("-" * 60)

    client, model = _gemini_client(model_name)
    personas = get_personas(mode, audience_config, persona_count)
    reference_data = get_reference_data(dimensions)
    rater = _build_rater(reference_data)

    print(f"Personas built: {len(personas)}")
    print(f"Dimensions: {', '.join(dimensions)}")

    all_results = {}
    all_responses = {}

    primary_results, primary_responses = _run_for_stimulus(
        "Primary", stimulus, personas, rater, dimensions, client, model
    )
    all_results["Primary"] = primary_results
    all_responses["Primary"] = (primary_responses, primary_results)

    if competitor:
        comp_results, comp_responses = _run_for_stimulus(
            "Competitor", competitor, personas, rater, dimensions, client, model
        )
        all_results["Competitor"] = comp_results
        all_responses["Competitor"] = (comp_responses, comp_results)

    # Print summary to console
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for label, results in all_results.items():
        print(f"\n{label}:")
        for dim_id, data in results.items():
            print(f"  {dim_id:<30} {data['expected']}/5")

    if len(all_results) == 2:
        print("\nGAP (Primary - Competitor):")
        for dim_id in dimensions:
            p = all_results["Primary"][dim_id]["expected"]
            c = all_results["Competitor"][dim_id]["expected"]
            gap = round(p - c, 2)
            sign = "+" if gap >= 0 else ""
            print(f"  {dim_id:<30} {sign}{gap}")

    # Save outputs
    print()
    report_content = generate_report(config, all_results, timestamp)
    report_path = Path(output_dir) / f"{timestamp}-report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"Report: {report_path}")

    _save_pmf_csv(all_results, output_dir, timestamp)
    _save_responses_csv(all_responses, output_dir, timestamp)

    print(f"\nAll outputs saved to: {output_dir}/")


if __name__ == "__main__":
    main()
