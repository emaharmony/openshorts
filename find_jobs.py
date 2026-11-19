import json

try:
    import app  # noqa

    candidates = [
        "_JOBS", "JOBS", "jobs", "MEM_JOBS", "_MEM_JOBS", "job_registry", "JOBS_DB",
    ]
    for c in candidates:
        obj = getattr(app, c, None)
        if obj is not None:
            print("FOUND:", c, type(obj))
            if hasattr(obj, "keys"):
                try:
                    keys = list(obj.keys())
                    print("keys sample:", keys[:20])
                    if "95708adc-c0f9-4550-85cd-ea1b91c6d35d" in keys:
                        job = obj["95708adc-c0f9-4550-85cd-ea1b91c6d35d"]
                        with open("/tmp/job_95708.json", "w") as f:
                            json.dump(job, f, default=str, indent=2)
                        print("job dumped to /tmp/job_95708.json")
                except Exception as e:
                    print("iter err:", e)
except Exception as e:
    print("import err:", e)