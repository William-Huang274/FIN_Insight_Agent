"""Project explicitly submitted research prose, never hidden provider reasoning."""


def submitted_prose(name, args):
    if not isinstance(args, dict):
        return None
    key = {"submit_case_report": "report", "submit_research_synthesis": "synthesis",
           "submit_case_answer": "answer", "submit_report_review": "review",
           "submit_case_review": "review"}.get(name)
    value = args if name in {"SubmitWorkpaperAction", "submit_workpaper"} else args.get(key) if key else None
    if not isinstance(value, dict):
        return None
    text = value.get("narrative_markdown") or value.get("summary")
    return text if isinstance(text, str) and text.strip() else None
