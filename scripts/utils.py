import subprocess


def execute(args):
    print("Executing: " + " ".join(args))
    try:
        logs = subprocess.run(args, check=True, capture_output=True)
        for line in logs.stdout.decode("utf-8").splitlines():
            print(f"  {line}")

        return logs
    except subprocess.CalledProcessError as e:
        print(f"  Failed: {e}")
        raise e
