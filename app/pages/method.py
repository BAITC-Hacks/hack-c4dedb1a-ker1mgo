"""Inspect exported method evidence without rerunning analytical calculations."""

import pandas as pd
import streamlit as st

from app.ui import OUT, get_store, page_header, read_json, read_table


def exported_json(name: str) -> dict:
    path = OUT / name
    try:
        return read_json(str(path), path.stat().st_mtime_ns) if path.exists() else {}
    except (OSError, ValueError):
        command = "make bench" if name == "bench_metadata.json" else "make run"
        st.warning(
            f"Could not read {name}. Wait for the export to finish, then refresh; `{command}` can rebuild this evidence."
        )
        return {}


def exported_csv(name: str) -> pd.DataFrame:
    path = OUT / name
    try:
        return read_table(str(path), path.stat().st_mtime_ns) if path.exists() else pd.DataFrame()
    except (OSError, ValueError):
        command = "make bench" if name == "bench.csv" else "make eval"
        st.warning(
            f"Could not read {name}. Wait for the export to finish, then refresh; `{command}` can regenerate this optional evidence."
        )
        return pd.DataFrame()


page_header(
    "Method & scale",
    "Inspect the measurements, assumptions and limits behind each case hypothesis.",
)
store = get_store()
model = exported_json("truncation_model.json")
metadata = exported_json("pipeline_metadata.json")
bench = exported_csv("bench.csv")

overview = st.columns(3)
overview[0].metric("Clients in this crawl", f"{len(store.f):,}")
overview[1].metric("Depth-4 clients with unknown outflow", f"{int(store.f.depth.eq(4).sum()):,}")
overview[2].metric(
    "Forwarding model · CV AUC",
    f"{model['auc_cv']:.3f}" if model.get("auc_cv") is not None else "Not measured",
)
st.caption(
    "Roles are explainable hypotheses. Cross-validation measures forwarding prediction, not the accuracy of the roles."
)

scale_tab, evidence_tab, provenance_tab = st.tabs(
    ["Measured scale", "Evidence & limits", "Method & provenance"]
)

with scale_tab:
    st.subheader("What happens as the graph grows")
    st.write(
        "Synthetic graph lifts preserve the empirical incoming and outgoing degree distributions "
        "and transfer amounts. They test computational cost; they do not establish accuracy on a larger investigation."
    )
    if bench.empty:
        st.info(
            "No benchmark export is available yet. Run `make bench`, then refresh this page to inspect measured timings."
        )
    else:
        chart = OUT / "bench.svg"
        if chart.exists():
            st.image(str(chart), width=900)
            st.download_button(
                "Download scale chart", chart.read_bytes(), "moneygraph-scale.svg", "image/svg+xml"
            )
        else:
            totals = bench[bench.step.eq("total")]
            if len(totals):
                st.line_chart(
                    totals.pivot_table(
                        index="nodes", columns="mode", values="seconds", aggfunc="median"
                    ),
                    x_label="Nodes",
                    y_label="Seconds",
                )
        st.caption(
            "Read each mode separately. Sampled betweenness trades precision for runtime; "
            "those timings are not an exact-mode forecast. A single run is a measurement, not a confidence interval."
        )
        st.caption(
            "The benchmark covers the core pipeline and exports. Interactive explanation files, input parquet copies and UI rendering are excluded; the full case runtime is recorded under Method & provenance."
        )
        st.subheader("Time spent in each step")
        modes = [mode for mode in sorted(bench["mode"].dropna().unique()) if mode != "before"]
        mode = st.selectbox(
            "Benchmark mode",
            modes,
            index=modes.index("sampled") if "sampled" in modes else 0,
            key="method_bench_mode",
        )
        subset = bench[bench["mode"].eq(mode)]
        timing = subset.pivot_table(
            index="step", columns="nodes", values="seconds", aggfunc="median"
        ).round(3)
        timing.columns = [f"{int(nodes):,} nodes · seconds" for nodes in timing.columns]
        st.dataframe(timing, width="stretch")
        quality_columns = [
            c
            for c in [
                "scale",
                "nodes",
                "edges",
                "transactions",
                "degree_distribution",
                "amount_distribution",
            ]
            if c in bench
        ]
        st.subheader("Workload and distribution checks")
        st.dataframe(subset[quality_columns].drop_duplicates(), hide_index=True, width="stretch")
        st.download_button(
            "Download measurements", bench.to_csv(index=False), "bench.csv", "text/csv"
        )
        reference = bench[bench.step.eq("temporal_reference")]
        optimized = bench[bench.step.eq("temporal") & bench["mode"].eq("exact") & bench.scale.eq(1)]
        if len(reference) and len(optimized):
            before, after = reference.seconds.median(), optimized.seconds.median()
            st.subheader("Measured improvement: temporal features")
            st.write(
                f"At the original case size, the earlier implementation took {before:.3f} s and the optimized one took {after:.3f} s ({before / after:.1f}× faster). The benchmark verifies identical temporal outputs for that comparison."
            )
        environment = exported_json("bench_metadata.json")
        if environment:
            with st.expander("Measurement environment and mode settings"):
                st.json(environment)
    st.write(
        "The next scale step is columnar aggregation with Polars or DuckDB, compiled graph algorithms, "
        "sampled centrality, and incremental updates. The viewer already shows bounded neighbourhoods. "
        "Million-node performance has not been measured here."
    )

with evidence_tab:
    st.subheader("An unseen exit is not evidence that money stopped")
    details = store.f.role_detail.value_counts()
    comparison = pd.DataFrame(
        [
            {
                "Approach": "Naive: every node with no observed outgoing transfer is a terminal",
                "Result": f"{int(store.f.depth.eq(4).sum()):,} unverified depth-4 sinks would be labelled terminal",
            },
            {
                "Approach": "Observed outgoing crawl at depths 1–3",
                "Result": f"{int(details.get('terminal_observed', 0)):,} observed terminal-role hypotheses",
            },
            {
                "Approach": "Model applied only where outgoing transfers were not crawled",
                "Result": f"{int(details.get('terminal_inferred', 0)):,} inferred terminal-role hypotheses; remaining nodes keep uncertainty labels",
            },
        ]
    )
    st.dataframe(comparison, hide_index=True, width="stretch")
    if model:
        st.write(
            f"A logistic regression learns forwarding from {int(model.get('n_train', 0)):,} non-seed clients "
            "at depths 1–3 using inbound-only features. Five-fold stratified cross-validation checks "
            "whether those features rank forwarders above non-forwarders. A base-rate correction adjusts "
            "the probabilities after fitting with balanced class weights."
        )
        rates = st.columns(2)
        rates[0].metric(
            "Observed forwarding · depths 1–3", f"{model.get('observed_rate_depth1_3', 0):.1%}"
        )
        rates[1].metric(
            "Mean predicted forwarding · depth 4", f"{model.get('mean_p_depth4', 0):.1%}"
        )
        with st.expander("Model coefficients and training record"):
            coefficients = pd.DataFrame(
                model.get("coefficients", {}).items(),
                columns=["Feature", "Standardized coefficient"],
            )
            st.dataframe(coefficients, hide_index=True, width="stretch")
            st.json({key: value for key, value in model.items() if key != "coefficients"})
        st.caption(
            "Depth 4 may differ from the training depths. Inferred terminals remain hypotheses; request the next crawl to check them."
        )

    st.subheader("Does the ranking interrupt seed-money flow?")
    resilience = store.resilience()
    if len(resilience):
        strategy_labels = {
            "priority": "Priority",
            "degree": "Degree (all clients)",
            "degree_nonseed": "Degree (seeds excluded)",
            "random": "Random (mean)",
        }
        curve = resilience.pivot(
            index="n_removed", columns="strategy", values="seed_flow_reach"
        ).rename(columns=strategy_labels)
        st.line_chart(
            curve, x_label="Clients removed", y_label="Share of seed-money flow remaining"
        )
        last = resilience[resilience.n_removed.eq(resilience.n_removed.max())].copy()
        last["strategy"] = last.strategy.replace(strategy_labels)
        last["seed_flow_reach"] = last.seed_flow_reach.map(lambda value: f"{value:.1%}")
        st.dataframe(
            last.rename(
                columns={
                    "n_removed": "Removed",
                    "strategy": "Strategy",
                    "largest_wcc": "Largest component",
                    "n_components": "Components",
                    "seed_flow_reach": "Flow remaining",
                }
            ),
            hide_index=True,
            width="stretch",
        )
        st.write(
            "Degree can fragment the graph more strongly, and removing seeds also removes the money's sources. "
            "Compare priority against degree with seeds excluded when assessing who to investigate beyond known seeds. "
            "This is a removal simulation, not evidence of a real-world intervention's effect."
        )
    else:
        st.info("Run `make run` to export the resilience comparison.")

    st.subheader("Limits to carry into an investigation")
    st.dataframe(
        pd.DataFrame(
            [
                (
                    "Four-hop, outgoing-only crawl",
                    "Unseen outgoing transfers and external inflows prevent balance claims.",
                ),
                (
                    "Seed inflow is incomplete",
                    "Seeds do not use inflow or pass-through in role conditions.",
                ),
                (
                    "Transfers below 5,000 KZT are missing",
                    "Splitting transfers below that threshold cannot be detected.",
                ),
                (
                    "No labelled roles or client attributes",
                    "Role scores describe rule strength, not the probability of wrongdoing.",
                ),
                (
                    "Approximate seed-money attribution",
                    "KZT-weighted propagation cannot identify which incoming funds financed a transfer.",
                ),
                (
                    "Undirected communities",
                    "Cluster membership groups connected clients and is not a statement about control.",
                ),
            ],
            columns=["Limit", "Analyst implication"],
        ),
        hide_index=True,
        width="stretch",
    )

with provenance_tab:
    st.subheader("From transfers to a reviewable dossier")
    st.code(
        "Raw transfers → structural + temporal metrics → seed-money flow\n             → forwarding model → ordered role rules\n             → communities + priority → exported case evidence",
        language=None,
    )
    st.write(
        "The pipeline runs offline and writes the case outputs. The viewer and optional assistant read those outputs. "
        "Each dossier exposes the matched rule, values against thresholds, the nearest missed rule, "
        "priority contributions and estimated seed-money paths. Role traces use the same configured predicates as role assignment."
    )
    if metadata:
        timings = metadata.get("step_timings", {})
        if timings:
            st.subheader("This case's pipeline run")
            runtime = metadata.get("total_seconds")
            if runtime is not None:
                st.metric("Full pipeline runtime", f"{runtime:.2f} s")
            st.dataframe(
                pd.DataFrame(timings.items(), columns=["Step", "Seconds"]),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                f"Centrality mode: {metadata.get('centrality_mode', 'not recorded')}. Timings include the exported case evidence."
            )
        if metadata.get("flow_semantics"):
            st.write(metadata["flow_semantics"])
        config = metadata.get("config", metadata.get("thresholds", {}))
        with st.expander("Thresholds and weights used for this export", expanded=False):
            st.json(config or metadata)
        with st.expander("Pipeline run record"):
            st.json(
                {
                    key: value
                    for key, value in metadata.items()
                    if key not in {"config", "thresholds"}
                }
            )
    else:
        st.info(
            "This export has no pipeline provenance record. Run `make run` to refresh the case outputs."
        )
    st.subheader("Guarded questions, optional connection")
    st.write(
        "The assistant queries exported evidence through bounded graph tools. It cannot assign a role or priority. "
        "Cited identifiers are checked against the graph; unknown identifiers trigger one rewrite and are masked if still unknown. "
        "The evaluation uses questions generated from the graph and compares cited identifiers with computed answers. "
        "Identifier checks do not establish that every sentence is correct."
    )
    evaluation = exported_csv("agent_eval.csv")
    if len(evaluation):
        st.dataframe(evaluation, hide_index=True, width="stretch")
    else:
        st.caption(
            "No assistant evaluation file is present in this export. Run `make eval` with an optional model connection to create one."
        )
