import pandas as pd
import requests
from io import StringIO
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

STATE_CODES = [
    "PLS","KDH","PNG","PRK","SEL","WLH","PTJ","NSN","MLK","JHR",
    "PHG","TRG","KEL","SRK","SAB","WLP"
]

DESIRED_COLUMNS = [
    "Station Name Station Name",
    "District District",
    "Main Basin Main Basin",
    "Sub River Basin Sub River Basin",
    "Last Updated Last Updated",
    "Water Level (m) (Graph) Water Level (m) (Graph)",
    "state_code",
]

SOURCE_URL = "https://publicinfobanjir.water.gov.my/aras-air/?lang=en"
BASE = "https://publicinfobanjir.water.gov.my/aras-air/data-paras-air/aras-air-data/"
MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")

def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            " ".join([str(x).strip() for x in tup if str(x).strip() and str(x) != "nan"]).strip()
            for tup in df.columns.to_list()
        ]
    else:
        df.columns = [str(c).strip() for c in df.columns]
    return df

def fetch_state(state_code: str, *, danger_only: bool) -> pd.DataFrame:
    params = {"district":"ALL", "station":"ALL", "lang":"en", "state": state_code}
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()

    tables = pd.read_html(StringIO(r.text)) 
    if not tables:
        return pd.DataFrame()

    df = tables[0]
    df = flatten_columns(df)              
    if danger_only:
        danger_col = "Threshold Danger"
        level_col = "Water Level (m) (Graph) Water Level (m) (Graph)"
        if danger_col in df.columns and level_col in df.columns:
            level_vals = pd.to_numeric(df[level_col], errors="coerce")
            danger_vals = pd.to_numeric(df[danger_col], errors="coerce")
            mask = ((danger_vals > 0) & (level_vals >= danger_vals)).fillna(False)
            df = df.loc[mask].copy()

    df["state_code"] = state_code
    keep_cols = [c for c in DESIRED_COLUMNS if c in df.columns]
    if keep_cols:
        df = df[keep_cols]
    return df

def df_to_records(df: pd.DataFrame) -> list[dict]:
    cleaned = df.copy()
    last_updated_col = "Last Updated Last Updated"
    if last_updated_col in cleaned.columns:
        parsed = pd.to_datetime(cleaned[last_updated_col], errors="coerce", dayfirst=True)
        if parsed.notna().any():
            localized = parsed.dt.tz_localize(MY_TZ, nonexistent="NaT", ambiguous="NaT")
            cleaned[last_updated_col] = localized.dt.strftime("%d/%m/%Y %H:%M").where(parsed.notna(), None)
    cleaned = cleaned.where(pd.notnull(cleaned), None)
    return cleaned.to_dict(orient="records")

def run(*, danger_only: bool) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    all_data: list[pd.DataFrame] = []
    per_state: dict[str, pd.DataFrame] = {}

    for code in STATE_CODES:
        try:
            df = fetch_state(code, danger_only=danger_only)
            if df.empty:
                print(f"{code}: no table / empty")
                continue
            per_state[code] = df
            all_data.append(df)
            print(f"{code}: OK ({len(df)} rows)")
        except Exception as e:
            print(f"{code}: failed -> {e}")

    if not all_data:
        raise SystemExit("No data returned for any state codes.")

    combined = pd.concat(all_data, ignore_index=True)
    return combined, per_state

def write_json(path: Path, combined: pd.DataFrame, per_state: dict[str, pd.DataFrame]) -> None:
    payload = {
        "generated_at": datetime.now(MY_TZ).strftime("%d/%m/%Y %H:%M"),
        "source": SOURCE_URL,
        "rows": int(len(combined)),
        "all": df_to_records(combined),
        "states": {code: df_to_records(df) for code, df in per_state.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def write_xlsx(path: Path, combined: pd.DataFrame, per_state: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        combined.to_excel(writer, sheet_name="ALL_STATES", index=False)
        for code, df in per_state.items():
            df.to_excel(writer, sheet_name=code, index=False)

def main() -> None:
    parser = argparse.ArgumentParser(description="Extract publicinfobanjir water level data.")
    parser.add_argument("--json", default="docs/data.json", help="Output JSON path.")
    parser.add_argument("--xlsx", default=None, help="Optional output XLSX path.")
    parser.add_argument(
        "--danger-only",
        action="store_true",
        help="Keep only stations where Water Level >= Threshold Danger (when available).",
    )
    args = parser.parse_args()

    combined, per_state = run(danger_only=args.danger_only)

    json_path = Path(args.json)
    write_json(json_path, combined, per_state)
    print(f"\nSaved JSON to {json_path}")

    if args.xlsx:
        xlsx_path = Path(args.xlsx)
        write_xlsx(xlsx_path, combined, per_state)
        print(f"Saved XLSX to {xlsx_path}")

if __name__ == "__main__":
    main()
