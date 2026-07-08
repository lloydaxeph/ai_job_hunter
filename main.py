import argparse

from Config import load_config
from Constants import JobAgentModes
from JobAgent import JobAgent
from Models.JobObject import  JobObject


def main(mode: JobAgentModes, max_jobs: int, debug: dict = {}):
    cfg = load_config()
    keyword_num = len(cfg["search"]["keywords"])
    location_num = len(cfg["search"]["locations"])
    if max_jobs:
        max_results_per_site = max_jobs // (keyword_num * location_num)
        cfg["search"]["max_results_per_site"] = max_results_per_site
    total_expected_jobs = int(cfg["search"]["max_results_per_site"]) * (keyword_num * location_num)

    print("JobHunter Agent INITIATED!")
    print(f"MODE: {mode}")
    bot = JobAgent(cfg)
    if mode != JobAgentModes.DEBUG:
        print(f"TOTAL EXPECTED JOBS: {total_expected_jobs}")
        bot.run(mode)
    else:
        debug_job = JobObject(
            title=debug["title"],
            company=debug["company"],
            url=debug["url"],
            site=debug["site"],
        )
        bot.debug(job=debug_job)
    print(f"----------------------------------------------------")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Override runtime options",
    )

    args = parser.parse_args()

    options = {}

    for item in args.set:
        key, value = item.split("=", 1)
        options[key] = value

    mode = JobAgentModes.QUICK_APPLY
    max_jobs = None
    debug = {}

    if "mode" in options:
        mode = options["mode"]

    if "max_jobs" in options:
        max_jobs = int(options["max_jobs"])

    main(mode=mode, max_jobs=max_jobs, debug=debug)

    #sample command
    # python main.py --set mode=quick_apply --set max_jobs=10