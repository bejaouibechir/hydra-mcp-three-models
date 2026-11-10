# reference (scripted (no model))

> In data/shop.db, the orders table holds every order and the customers table holds each customer's country. Build a Hydra ETL job in jobs/revenue_by_country that reports, for each country, the number of paid orders and their total amount: only orders with status 'paid', total rounded to 2 decimals, sorted from the highest revenue to the lowest. Write the result to outputs/revenue_by_country.csv with exactly the columns country, orders, revenue. Then run the job and check the result.

**model** (3.6s)

(scripted reference run: no model, the expected tool calls)

**→ hydra_preview_data** (3.6s)

```json
{
  "file_path": "data/shop.db"
}
```

```text
Database: data/shop.db
Tables:
- customers (300 rows): customer_id INTEGER, name TEXT, country TEXT
- orders (2000 rows): order_id INTEGER, customer_id INTEGER, ordered_at TEXT, amount TEXT, status TEXT

Give `table` to see the first rows of a table.

In a job: type: sqlite, connection.path relative to the job folder.
```

**→ hydra_list_operations** (3.6s)

```json
{}
```

```text
aggregate      required: by, agg
calculate      required: column, expr
cast           required: mapping
clean          required: —
deduplicate    required: —
fill_null      required: —
filter         required: expr
join           required: right
merge          required: right, key
pivot          required: index, column, values
rename         required: mapping
script         required: outputs, code
select         required: columns
sort           required: by
text_to_rows   required: column
transpose      required: —
trim           required: —
union          required: right
unpivot        required: id_vars
window         required: columns
```

**→ hydra_write_job** (4.0s)

```json
{
  "job_path": "jobs/revenue_by_country",
  "sources_yaml": "version: \"1.0\"\nsources:\n  orders:\n    type: sqlite\n    connection:\n      path: ../../data/shop.db\n    extract:\n      table: orders\n  customers:\n    type: sqlite\n    connection:\n      path: ../../data/shop.db\n    extract:\n      table: customers\n",
  "transformations_yaml": "version: \"1.0\"\nsteps:\n  - filter:\n      expr: \"status == 'paid'\"\n  - cast:\n      mapping:\n        amount: float\n  - join:\n      right: customers\n      key: customer_id\n      how: inner\n  - aggregate:\n      by: [country]\n      agg:\n        orders: {func: count, col: order_id}\n        revenue: {func: sum, col: amount}\n  - calculate:\n      column: revenue\n      expr: \"round(revenue, 2)\"\n  - sort:\n      by: [revenue]\n      ascending: false\n  - select:\n      columns: [country, orders, revenue]\n",
  "destinations_yaml": "version: \"1.0\"\ndestinations:\n  report:\n    type: csv\n    load:\n      table: ../../outputs/revenue_by_country.csv\n      mode: replace\n",
  "pipeline_yaml": "version: \"1.0\"\npipeline:\n  from: orders\n  to: report\n"
}
```

```text
WRITTEN to jobs/revenue_by_country: destinations.yaml, pipeline.yaml, sources.yaml, transformations.yaml.
The job is valid. It was not run — use hydra_run_job if the user asks for it.
```

**→ hydra_check_job** (5.0s)

```json
{
  "user_request": "In data/shop.db, the orders table holds every order and the customers table holds each customer's country. Build a Hydra ETL job in jobs/revenue_by_country that reports, for each country, the number of paid orders and their total amount: only orders with status 'paid', total rounded to 2 decimals, sorted from the highest revenue to the lowest. Write the result to outputs/revenue_by_country.csv with exactly the columns country, orders, revenue. Then run the job and check the result.",
  "job_path": "jobs/revenue_by_country"
}
```

```text
NO ALERT — the job looks consistent with the request. Present it to the user.
```

**→ hydra_run_job** (5.1s)

```json
{
  "job_path": "jobs/revenue_by_country"
}
```

```text
RUN SUCCEEDED
DevOps Edition  v0.20.0  ────────────────────────────
  ▶  Pipeline  revenue_by_country  — jobs/revenue_by_country
  ✅ Pipeline completed successfully in 3.0s
  Rows read   : 2,000
  Rows written: 8

Output produced:
- report: ../../outputs/revenue_by_country.csv — 8 rows, 3 columns (country, orders, revenue)
```

**→ hydra_preview_data** (9.9s)

```json
{
  "file_path": "outputs/revenue_by_country.csv",
  "rows": 10
}
```

```text
File: outputs/revenue_by_country.csv
Columns: country (object), orders (int64), revenue (float64)
Total rows: 8

First 10 rows:
country  orders   revenue
  Italy     258 121151.67
Belgium     238 110779.97
 Canada     241 110332.47
Morocco     219  99527.67
 France     180  85075.75
  Spain     184  84303.74
Germany     176  77537.33
Tunisia     134  59638.26

Reminder: a CSV file carries no types. The types above are guessed by the reader, not guaranteed — put a `cast` before any numeric comparison.
```

**model** (9.9s)

Job written, checked and run.

## Result

- check: OK
- tool calls: 6, writes refused by Hydra ETL: 0, failed runs: 0, alerts: 0
- duration: 10.2 s, model turns: 0, tokens: 0 in / 0 out
- stopped: script finished
