import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from _common import iter_data_sheets

RAW = Path(__file__).resolve().parents[2] / "raw" / "2024" / "Food chemistry section.xlsx"

# NOTE: a minimal "columns" mapping (sample_id -> "Sample ID") is required here.
# Without any "columns" entry, iter_data_sheets' col_map stays empty for every
# sheet, so "any_value" is never True and no sheet ever yields a row (see
# _common.py's row-building loop) -- independent of only_sheets. This addition
# is needed so the test actually exercises the whitelist rather than always
# failing on an unrelated empty-col_map short-circuit.

# With only_sheets, exactly the "Jams " sheet is read out of the 15-sheet file.
schema = {"single_sheet": True, "only_sheets": ["Jams"], "header_row_max": 4,
          "columns": {"sample_id": ["Sample ID"]}}
sheets = {sn for sn, ym, rows in iter_data_sheets(RAW, 2024, schema)}
assert sheets == {"Jams "}, f"only_sheets should yield just 'Jams ', got {sheets!r}"

# Without only_sheets, single_sheet reads more than one sheet (whitelist really filters).
schema_open = {"single_sheet": True, "header_row_max": 4,
               "columns": {"sample_id": ["Sample ID"]}}
sheets_open = {sn for sn, ym, rows in iter_data_sheets(RAW, 2024, schema_open)}
assert len(sheets_open) > 1, f"expected multiple sheets without whitelist, got {sheets_open!r}"

print("ONLY_SHEETS PASS")
