import sys

sys.path.insert(0, "arachne")

try:
    import clips
except ImportError:
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "clipspy", "--quiet"])
    import clips

env = clips.Environment()
try:
    env.load("arachne/rulebase.clp")
    rules = list(env.rules())
    names = [r.name for r in rules]
    duplicates = [n for n in names if names.count(n) > 1]
    if duplicates:
        print(f"DUPLICATE RULE NAMES: {set(duplicates)}")
        sys.exit(1)
    print(f"OK — {len(rules)} rules loaded, 0 duplicates")
except Exception as e:
    print(f"CLIPS ERROR: {e}")
    sys.exit(1)
