import streamlit as st

from app.ui import get_store, node_table, page_header

store = get_store()
page_header("Ask for the evidence that is missing.", "Specific follow-up requests to resolve the crawl’s blind spots. Each request links back to a client dossier.")
requests = store.data_requests
if requests.empty:
    st.info("No data requests are available. Run `make run` to rebuild the case outputs.")
    st.stop()
a, b, c = st.columns(3)
a.metric("Clients with follow-up requests", f"{requests.gid.nunique():,}")
b.metric("Request categories", requests.reason.nunique())
c.metric("Uncrawled depth-4 clients", int(store.f.depth.eq(4).sum()))
reason = st.selectbox("Request category", ["All requests"] + sorted(requests.reason.unique()), format_func=lambda x: x.replace("_", " "))
rows = requests if reason == "All requests" else requests[requests.reason.eq(reason)]
node_table(rows, "request_queue", ["gid", "reason", "suggested_request"])
st.download_button("Download selected data requests", rows.to_csv(index=False), "data_requests.csv", "text/csv")
st.caption("Transfers below 5,000 KZT and transfers outside this bank are absent. No interface can reconstruct them from the visible graph.")
