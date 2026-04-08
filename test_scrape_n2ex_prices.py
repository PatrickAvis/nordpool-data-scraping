import unittest

from scrape_n2ex_prices import (
    half_hourly_rows,
    output_fieldnames,
    parse_portal_price,
    pivot_grid,
    rows_for_csv,
    settlement_period_for_period,
    with_london_datetime,
    with_settlement_period,
)


class TestScrapeTransforms(unittest.TestCase):
    def test_rows_for_csv_uses_previous_day_for_2300(self) -> None:
        rows = [
            {"period": "23:00 - 00:00", "price": 89.78},
            {"period": "00:00 - 01:00", "price": 93.11},
        ]

        out = rows_for_csv(rows, "2026-04-08")

        self.assertEqual(out[0]["deliverydate"], "2026-04-07")
        self.assertEqual(out[0]["start_t"], "23:00")
        self.assertEqual(out[0]["price_gbp_mwh"], 89.78)
        self.assertEqual(out[1]["deliverydate"], "2026-04-08")
        self.assertEqual(out[1]["start_t"], "00:00")

    def test_half_hourly_rows_duplicates_and_sorts(self) -> None:
        base_rows = [
            {"deliverydate": "2026-04-08", "start_t": "00:00", "price_gbp_mwh": 1.0},
            {"deliverydate": "2026-04-07", "start_t": "23:00", "price_gbp_mwh": 2.0},
        ]

        out = half_hourly_rows(base_rows)

        self.assertEqual(len(out), 4)
        self.assertEqual(
            [(r["deliverydate"], r["start_t"]) for r in out],
            [
                ("2026-04-07", "23:00"),
                ("2026-04-07", "23:30"),
                ("2026-04-08", "00:00"),
                ("2026-04-08", "00:30"),
            ],
        )

    def test_settlement_period_mapping(self) -> None:
        self.assertEqual(settlement_period_for_period("23:00"), 47)
        self.assertEqual(settlement_period_for_period("23:30"), 48)
        self.assertEqual(settlement_period_for_period("00:00"), 1)
        self.assertEqual(settlement_period_for_period("22:30"), 46)
        self.assertIsNone(settlement_period_for_period("12:15"))
        self.assertIsNone(settlement_period_for_period("not-a-time"))

    def test_with_settlement_period_adds_column(self) -> None:
        rows = [
            {"deliverydate": "2026-04-07", "start_t": "23:00", "price_gbp_mwh": 89.78},
            {"deliverydate": "2026-04-07", "start_t": "23:30", "price_gbp_mwh": 89.78},
        ]

        out = with_settlement_period(rows)
        self.assertEqual(out[0]["settlement_period"], 47)
        self.assertEqual(out[1]["settlement_period"], 48)

    def test_with_london_datetime_adds_start_dt(self) -> None:
        rows = [
            {"deliverydate": "2026-01-15", "start_t": "23:00", "price_gbp_mwh": 89.78},
            {"deliverydate": "2026-01-16", "start_t": "00:30", "price_gbp_mwh": 93.11},
        ]

        out = with_london_datetime(rows)
        self.assertEqual(out[0]["start_dt"], "2026-01-15T23:00+00:00")
        self.assertEqual(out[1]["start_dt"], "2026-01-16T00:30+00:00")

    def test_with_london_datetime_uses_bst_offset_in_summer(self) -> None:
        rows = [{"deliverydate": "2026-07-15", "start_t": "12:00", "price_gbp_mwh": 50.0}]

        out = with_london_datetime(rows)

        self.assertEqual(out[0]["start_dt"], "2026-07-15T12:00+01:00")

    def test_with_london_datetime_handles_invalid_input(self) -> None:
        rows = [
            {"deliverydate": "bad-date", "start_t": "12:00", "price_gbp_mwh": 10.0},
            {"deliverydate": "2026-01-15", "start_t": "bad-time", "price_gbp_mwh": 10.0},
        ]

        out = with_london_datetime(rows)

        self.assertEqual(out[0]["start_dt"], "")
        self.assertEqual(out[1]["start_dt"], "")

    def test_parse_portal_price_handles_common_formats(self) -> None:
        self.assertEqual(parse_portal_price("89,20"), 89.2)
        self.assertEqual(parse_portal_price(" 1 234,56 "), 1234.56)
        self.assertIsNone(parse_portal_price("-"))
        self.assertIsNone(parse_portal_price("N/A"))

    def test_end_to_end_half_hourly_row_count_is_48(self) -> None:
        rows = [{"period": "23:00 - 00:00", "price": 1.0}]
        for h in range(23):
            rows.append({"period": f"{h:02d}:00 - {(h + 1):02d}:00", "price": 1.0})

        hourly = rows_for_csv(rows, "2026-04-08")
        half_hourly = half_hourly_rows(hourly)

        self.assertEqual(len(hourly), 24)
        self.assertEqual(len(half_hourly), 48)

    def test_output_fieldnames_hourly_order(self) -> None:
        self.assertEqual(
            output_fieldnames(half_hourly=False),
            ["start_dt", "deliverydate", "start_t", "price_gbp_mwh"],
        )

    def test_output_fieldnames_half_hourly_order(self) -> None:
        self.assertEqual(
            output_fieldnames(half_hourly=True),
            ["start_dt", "deliverydate", "start_t", "settlement_period", "price_gbp_mwh"],
        )

    def test_pivot_grid_builds_expected_matrix(self) -> None:
        rows = [
            {"deliverydate": "2026-04-07", "settlement_period": 47, "price_gbp_mwh": 89.78},
            {"deliverydate": "2026-04-07", "settlement_period": 48, "price_gbp_mwh": 90.01},
            {"deliverydate": "2026-04-08", "settlement_period": 1, "price_gbp_mwh": 93.11},
            {"deliverydate": "2026-04-08", "settlement_period": 2, "price_gbp_mwh": 94.12},
        ]

        periods, matrix = pivot_grid(rows)

        self.assertEqual(periods, [1, 2, 47, 48])
        self.assertEqual(matrix[0], ["2026-04-07", "", "", 89.78, 90.01])
        self.assertEqual(matrix[1], ["2026-04-08", 93.11, 94.12, "", ""])


if __name__ == "__main__":
    unittest.main()
