# Money graph

Hackathon team repository for ker1mGo, case «Граф денег»: recover the structure of a money network from a
4-hop graph of outgoing transfers, assign roles, cluster it, and rank who an AML analyst should look at first.

## Quickstart

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make run      # project_docs/data -> out/nodes_roles.csv, clusters.csv, top_nodes.csv
make test
make app      # viewer on http://localhost:8501
```

Work in progress. Design: [docs/design.md](docs/design.md) · how we work: [CONTRIBUTING.md](CONTRIBUTING.md).
