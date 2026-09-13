"""Command line interface for Epicenter."""

import os
import sys

from .graph import CodeGraph

# ─── CLI ────────────────────────────────────────────────────────────────────

def _indexed_realms(db_path):
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        realms = [r[0] for r in conn.execute("SELECT DISTINCT realm FROM nodes") if r[0]]
        conn.close()
        return realms
    except Exception:
        return []


def _default_realm(db_path):
    """
    Uses the only indexed realm if there is exactly one, so the common case
    needs no --realm flag.

    Returns None when several are indexed; the caller must refuse rather than
    query without one, since an unfiltered query silently merges every
    indexed codebase into a single graph and answers from the blend.
    """
    realms = _indexed_realms(db_path)
    return realms[0] if len(realms) == 1 else None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ask what breaks if you change something.")
    parser.add_argument("--db", default="epicenter.db")
    parser.add_argument("--realm", default=None, help="indexed codebase path")
    parser.add_argument("--external", action="store_true", help="include builtins and third-party symbols")

    sub = parser.add_subparsers(dest="command", required=True)

    p_impact = sub.add_parser("impact", help="what breaks if this changes")
    p_impact.add_argument("symbol")
    p_impact.add_argument("--depth", type=int, default=None)

    p_deps = sub.add_parser("deps", help="what this relies on")
    p_deps.add_argument("symbol")
    p_deps.add_argument("--depth", type=int, default=1)

    p_find = sub.add_parser("find", help="look up a symbol name")
    p_find.add_argument("query")

    p_index = sub.add_parser("index", help="parse a codebase into the graph")
    p_index.add_argument("path")

    p_hist = sub.add_parser("history", help="mine git history for change coupling")
    p_hist.add_argument("path", nargs="?", default=None)
    p_hist.add_argument("--max-commits", type=int, default=500)

    p_coup = sub.add_parser("coupling", help="symbols that change alongside this one")
    p_coup.add_argument("symbol")
    p_coup.add_argument("--min-confidence", type=float, default=0.3)

    sub.add_parser("stats", help="graph size")
    sub.add_parser("dead", help="symbols no entrypoint or test can reach")

    p_cov = sub.add_parser("coverage", help="which tests reach a symbol")
    p_cov.add_argument("symbol")

    args = parser.parse_args()

    # Indexing runs before any graph is loaded — there may not be one yet.
    if args.command == "index":
        from .pipeline import ingest_codebase

        target = os.path.abspath(os.path.expanduser(args.path))
        if not os.path.isdir(target):
            print(f"Not a directory: {target}")
            sys.exit(1)
        if not ingest_codebase(target, db_path=args.db):
            print(f"No Python files or no relationships found in {target}.")
            sys.exit(1)

        from .pipeline import parse_repository
        failures = getattr(parse_repository, "last_failures", [])

        stats = CodeGraph(db_path=args.db, realm=target).stats()
        print(f"Indexed {target}")
        for key in ("symbols", "dependency_edges", "entrypoints", "tests", "unreachable"):
            print(f"  {key:20} {stats[key]}")

        if failures:
            # Every symbol in an unparsed file is missing from the graph, so
            # this is never a detail to bury. Reported per file: a syntax
            # error trips both passes and would otherwise be listed twice.
            by_file = {}
            for path, _phase, message in failures:
                by_file.setdefault(path, message)
            print(f"\n  {len(by_file)} file(s) FAILED TO PARSE - their symbols are absent:")
            for path, message in list(by_file.items())[:5]:
                print(f"    {os.path.basename(path)}: {message}")
            if len(by_file) > 5:
                print(f"    ... and {len(by_file) - 5} more")
        return

    if args.command == "history":
        from .cochange import ingest_history

        target = args.path or args.realm or _default_realm(args.db)
        if target is None:
            print("Which codebase? Pass a path, or --realm.")
            sys.exit(1)
        target = os.path.abspath(os.path.expanduser(target))

        summary = ingest_history(target, db_path=args.db, max_commits=args.max_commits)
        if summary is None:
            print(f"No usable git history for {target}.")
            print("The directory must be inside a repository that tracks its Python files.")
            sys.exit(1)

        print(f"Analysed {summary['commits']} commit(s) of {target}")
        print(f"  {summary['symbols']} symbol(s) changed across them")
        print(f"  {summary['pairs']} co-change pair(s) recorded")
        if summary["commits"] < 20:
            print("\nThin history — coupling needs many commits before it means much.")
        return

    realm = args.realm or _default_realm(args.db)
    if realm is None:
        indexed = _indexed_realms(args.db)
        if not indexed:
            print("No codebase indexed yet. Run: epicenter index <path>")
        else:
            print("Several codebases are indexed; pass --realm to choose one:")
            for r in indexed:
                print(f"   {r}")
        sys.exit(1)

    graph = CodeGraph(db_path=args.db, realm=realm, include_external=args.external)

    if args.command == "stats":
        for key, value in graph.stats().items():
            print(f"{key:20} {value}")
        return

    if args.command == "dead":
        dead = graph.unreachable()
        roots = len(graph.reachability_roots())
        if not roots:
            print("No entrypoints or tests detected — every symbol would look dead.")
            print("Reachability needs roots: a __main__ guard, a route decorator, or tests.")
            return
        if not dead:
            print("Every symbol is reachable from an entrypoint or a test.")
            return
        print(f"{len(dead)} symbol(s) unreachable from any entrypoint or test:\n")
        for symbol in dead:
            print(f"   {symbol}  ({graph.node_types.get(symbol, 'unknown')})")
        print("\nCandidates only — unresolved calls can make live code look dead.")
        return

    if args.command == "find":
        matches = graph.find_symbol(args.query)
        if not matches:
            print(f"no symbol matching {args.query!r}")
            sys.exit(1)
        for m in matches:
            print(f"{m}  ({graph.node_types.get(m, 'unknown')})")
        return

    matches = graph.find_symbol(args.symbol)
    if not matches:
        print(f"no symbol matching {args.symbol!r}")
        sys.exit(1)
    if len(matches) > 1:
        print(f"{args.symbol!r} is ambiguous, using {matches[0]}")
        print("  other matches: " + ", ".join(matches[1:5]))
        print()
    target = matches[0]

    if args.command == "impact":
        results = graph.impact_of(target, max_depth=args.depth)
        if not results:
            print(f"Nothing depends on {target}. Safe to change.")
            return

        print(f"Changing {target} could affect {len(results)} symbol(s):\n")
        # With no tests at all, every symbol is trivially uncovered. Tagging
        # them would dress up an absence of information as a finding.
        has_tests = bool(graph.tests)
        current = None
        for item in results:
            if item.distance != current:
                current = item.distance
                label = "directly" if current == 1 else f"{current} hops away"
                print(f"  ── {label} ──")
            flag = "  ⚠" if item.fanin >= 5 else "   "
            cover = "  [UNTESTED]" if has_tests and not graph.is_covered(item.symbol) else ""
            print(f"{flag} {item.symbol}  ({item.node_type}, {item.fanin} dependents){cover}")
            if item.distance > 1:
                print(f"      via {' <- '.join(reversed(item.path))}")

        # History knows about coupling the call graph cannot: two symbols that
        # always change together with nothing calling anything.
        if graph.has_history:
            structural = {r.symbol for r in results} | {target}
            hidden = [
                c for c in graph.coupled_with(target, min_confidence=0.5)
                if c["symbol"] not in structural and not c["structural"]
            ]
            if hidden:
                print("\n  ── historically changed alongside, with no code path ──")
                for item in hidden[:5]:
                    print(f"     {item['confidence']:.0%}  ({item['together']}/{item['of_commits']})"
                          f"  {item['symbol']}")

        untested = [i for i in results if not graph.is_covered(i.symbol)]
        print()
        if not graph.tests:
            print("  No tests detected in this codebase, so coverage is unknown.")
        elif untested:
            print(f"  {len(untested)} of {len(results)} affected symbol(s) have no test reaching them.")
        else:
            print(f"  All {len(results)} affected symbol(s) are reached by some test.")
        print()

    elif args.command == "coupling":
        if not graph.has_history:
            print("No history analysed yet. Run: epicenter history")
            sys.exit(1)

        coupled = graph.coupled_with(target, min_confidence=args.min_confidence)
        if not coupled:
            print(f"Nothing changes with {target} often enough to report.")
            return

        print(f"Symbols that change alongside {target}:\n")
        for item in coupled:
            share = f"{item['together']}/{item['of_commits']}"
            tag = "" if item["structural"] else "   ← no code path between them"
            print(f"   {item['confidence']:.0%}  ({share})  {item['symbol']}{tag}")
        print("\nCorrelation from history, not a dependency. The flagged pairs are")
        print("the interesting ones: coupled in practice, invisible to the call graph.")
        return

    elif args.command == "coverage":
        covering = graph.tests_covering(target)
        if not graph.tests:
            print("No tests detected in this codebase.")
        elif covering:
            print(f"{target} is reached by {len(covering)} test(s):\n")
            for t in covering:
                print(f"   {t}")
            print("\nReachability, not assertion — a test touching this path may not check it.")
        else:
            print(f"No test reaches {target}.")
        return

    elif args.command == "deps":
        results = graph.dependencies_of(target, max_depth=args.depth)
        if not results:
            print(f"{target} depends on nothing local.")
            return
        print(f"{target} depends on {len(results)} symbol(s):\n")
        for item in results:
            print(f"   {item.symbol}  ({item.node_type})")
        print()


if __name__ == "__main__":
    main()
