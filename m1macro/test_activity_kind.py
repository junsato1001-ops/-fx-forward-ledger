"""IMPL-FINDINGS-11 F11-a (むすび 2026-10-19, required before candidate-2's Formal): the expected activity type of a
results commit is decided by its git topology, never "branch_creation OR push".

  root results commit (no parent)  -> activity_type = branch_creation, before = 40 zeros, after = Results_Commit
  results commit with a parent     -> activity_type = push,            before = parent,   after = Results_Commit

Fixtures are the REAL activity records GitHub produced for this repository:
  branch_creation 46968308924 (m1macro-gates-results, Formal run 39196332834, root commit 234accb8...)
  push            46955708825 (m1macro-dev-results, commit 8d46f84f... with parent 1b67dfef...)
plus end-to-end runs of freeze_record.gate_results on temporary repositories (root and non-root results commits) whose
activity lists are built in the same real shape. No network, no real data."""
import copy
import subprocess
import tempfile
from pathlib import Path

from m1macro import freeze_record as F
from m1macro.test_freeze_audit import CAND, CS, RUN, _formal_files
from m1macro.test_freeze_record import SNAP, _t
from m1macro.test_gitrepo_tx import _repo

BOT = {"login": "github-actions[bot]"}
REAL_CREATION = {"id": 46968308924, "activity_type": "branch_creation", "ref": "refs/heads/m1macro-gates-results",
                 "before": "0" * 40, "after": "234accb87ba890caa454ef9abf64e38e0a4fcf9f",
                 "timestamp": "2026-10-19T05:35:06Z", "actor": BOT}
REAL_PUSH = {"id": 46955708825, "activity_type": "push", "ref": "refs/heads/m1macro-dev-results",
             "before": "1b67dfef56ae532b58666dc0c37602f6c5f640cc", "after": "8d46f84f159c8af1ce44427f077a1de8c49e1122",
             "timestamp": "2026-10-19T02:18:31Z", "actor": BOT}


def _expect(fn, code):
    try:
        fn(); got = None
    except (F.PushNotFound, F.FreezeRefused) as e:
        got = str(e)
    assert got == code, (got, code)
    return f"FAIL:{code}"


def unit_real_events():
    out = {}
    C, P = REAL_CREATION, REAL_PUSH
    # positives: the topology-derived kind finds the real record
    assert F.find_push([C], C["after"], C["ref"], F.ZERO_SHA, F.ACTIONS_ACTOR, "branch_creation") == \
        ("46968308924", _t("2026-10-19T05:35:06"))
    assert F.find_push([P], P["after"], P["ref"], P["before"], F.ACTIONS_ACTOR, "push") == \
        ("46955708825", _t("2026-10-19T02:18:31"))
    out["root_branch_creation"] = out["nonroot_push"] = "PASS"
    # the kind is NOT interchangeable
    out["root_claimed_as_push"] = _expect(lambda: F.find_push([C], C["after"], C["ref"], C["before"], None, "push"),
                                          "PUSH_EVENT_NOT_FOUND")
    out["nonroot_claimed_as_creation"] = _expect(
        lambda: F.find_push([P], P["after"], P["ref"], F.ZERO_SHA, None, "branch_creation"), "PUSH_EVENT_NOT_FOUND")
    # before / after / ref / actor mismatches
    out["root_before_not_zero"] = _expect(
        lambda: F.find_push([C], C["after"], C["ref"], "1" * 40, None, "branch_creation"), "PUSH_EVENT_PARENT_MISMATCH")
    out["nonroot_before_wrong"] = _expect(
        lambda: F.find_push([P], P["after"], P["ref"], "1" * 40, None, "push"), "PUSH_EVENT_PARENT_MISMATCH")
    out["after_wrong"] = _expect(lambda: F.find_push([P], "2" * 40, P["ref"], P["before"], None, "push"),
                                 "PUSH_EVENT_NOT_FOUND")
    out["ref_wrong"] = _expect(lambda: F.find_push([P], P["after"], "refs/heads/m1macro-gates-results", P["before"],
                                                   None, "push"), "PUSH_EVENT_NOT_FOUND")
    out["actor_wrong"] = _expect(lambda: F.find_push([{**P, "actor": {"login": "junsato1001-ops"}}], P["after"],
                                                     P["ref"], P["before"], F.ACTIONS_ACTOR, "push"),
                                 "PUSH_EVENT_ACTOR_MISMATCH")
    out["two_records_same_after"] = _expect(lambda: F.find_push([P, {**P, "id": 1}], P["after"], P["ref"], P["before"],
                                                                None, "push"), "PUSH_EVENT_NOT_UNIQUE")
    out["kind_other"] = _expect(lambda: F.find_push([P], P["after"], P["ref"], P["before"], None, "force_push"),
                                "PUSH_EVENT_KIND_INVALID")
    return out


def _results_repo(td, name, n_commits):
    """A repository whose m1macro-gates-results branch holds n_commits commits, the last one carrying the formal
    results; returns (work dir, results commit, its parent or None)."""
    bare, work = _repo(td, name)
    git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", *a], cwd=work, check=True,
                                    capture_output=True).stdout.decode().strip()
    git("checkout", "-q", "--orphan", F.GATES_RESULTS_BRANCH); git("rm", "-rq", "--cached", ".")
    for i in range(n_commits - 1):
        Path(work, f"seed{i}").write_text(str(i)); git("add", f"seed{i}"); git("commit", "-qm", f"seed {i}")
        git("rm", "-rq", "--cached", ".")
    for n, b in _formal_files().items():
        p = Path(work, CS, n); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
    git("add", CS); git("commit", "-qm", "FORMAL gates"); rc = git("rev-parse", "HEAD")
    parent = git("rev-parse", "HEAD^") if n_commits > 1 else None
    git("push", "-q", "origin", F.GATES_RESULTS_BRANCH); git("checkout", "-q", "-f", "main")
    return work, rc, parent


def _api(events):
    """Fake GitHub APIs: the run record, and an activity list (real record shape) searched with the production
    find_push exactly as activity_lookup does for the requested kind."""
    def push(commit, parent, kind):
        evs = [e for e in events if e["activity_type"] == kind]      # the API filters by activity_type=<kind>
        return F.find_push(evs, commit, f"refs/heads/{F.GATES_RESULTS_BRANCH}", parent, F.ACTIONS_ACTOR, kind)
    return {"run": lambda i, a: RUN, "push": push}


def end_to_end():
    out = {}
    ref = f"refs/heads/{F.GATES_RESULTS_BRANCH}"
    with tempfile.TemporaryDirectory() as td:
        # root results commit
        work, rc, parent = _results_repo(td, "root", 1)
        assert parent is None
        creation = {**copy.deepcopy(REAL_CREATION), "ref": ref, "after": rc}
        r = F.gate_results(str(work), CS, CAND, SNAP, _api([creation]))
        assert r["Results_Push"] == {"Activity_ID": "46968308924", "At_Server_UTC": "2026-10-19T05:35:06Z"}, r
        out["e2e_root_branch_creation"] = "PASS"
        as_push = {**creation, "activity_type": "push"}
        out["e2e_root_only_push_record"] = _expect(lambda: F.gate_results(str(work), CS, CAND, SNAP, _api([as_push])),
                                                   "GATE_RESULTS_PUSH_EVENT_NOT_FOUND")
        out["e2e_root_creation_before_nonzero"] = _expect(
            lambda: F.gate_results(str(work), CS, CAND, SNAP, _api([{**creation, "before": "1" * 40}])),
            "GATE_RESULTS_PUSH_EVENT_PARENT_MISMATCH")
        out["e2e_root_creation_other_after"] = _expect(
            lambda: F.gate_results(str(work), CS, CAND, SNAP, _api([{**creation, "after": "2" * 40}])),
            "GATE_RESULTS_PUSH_EVENT_NOT_FOUND")
        out["e2e_root_creation_other_ref"] = _expect(
            lambda: F.gate_results(str(work), CS, CAND, SNAP, _api([{**creation, "ref": "refs/heads/m1macro-dev-results"}])),
            "GATE_RESULTS_PUSH_EVENT_NOT_FOUND")
        # non-root results commit
        work2, rc2, parent2 = _results_repo(td, "nonroot", 3)
        assert parent2 is not None
        push = {**copy.deepcopy(REAL_PUSH), "ref": ref, "before": parent2, "after": rc2}
        r = F.gate_results(str(work2), CS, CAND, SNAP, _api([push]))
        assert r["Results_Push"] == {"Activity_ID": "46955708825", "At_Server_UTC": "2026-10-19T02:18:31Z"}, r
        out["e2e_nonroot_push"] = "PASS"
        as_creation = {**push, "activity_type": "branch_creation", "before": F.ZERO_SHA}
        out["e2e_nonroot_only_creation_record"] = _expect(
            lambda: F.gate_results(str(work2), CS, CAND, SNAP, _api([as_creation])), "GATE_RESULTS_PUSH_EVENT_NOT_FOUND")
        out["e2e_nonroot_before_wrong"] = _expect(
            lambda: F.gate_results(str(work2), CS, CAND, SNAP, _api([{**push, "before": "1" * 40}])),
            "GATE_RESULTS_PUSH_EVENT_PARENT_MISMATCH")
        out["e2e_nonroot_other_after"] = _expect(
            lambda: F.gate_results(str(work2), CS, CAND, SNAP, _api([{**push, "after": "2" * 40}])),
            "GATE_RESULTS_PUSH_EVENT_NOT_FOUND")
        out["e2e_nonroot_other_ref"] = _expect(
            lambda: F.gate_results(str(work2), CS, CAND, SNAP, _api([{**push, "ref": "refs/heads/main"}])),
            "GATE_RESULTS_PUSH_EVENT_NOT_FOUND")
        out["e2e_nonroot_both_records_only_push_counts"] = "PASS" if F.gate_results(
            str(work2), CS, CAND, SNAP, _api([push, as_creation]))["Results_Push"]["Activity_ID"] == "46955708825" else "X"
    return out


def run():
    cases = {**unit_real_events(), **end_to_end()}
    assert "X" not in cases.values(), cases
    return {"ok": True, "cases": cases}


if __name__ == "__main__":
    print(run())
