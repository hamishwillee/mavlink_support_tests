# MAVLink Support Tests

A set of tests written in Libmav-python that test for things like:
- What messages are streamed by default
- What commands are supported, unsupported, or don't state either


To use:

```
git clone https://github.com/hamishwillee/mavlink_support_tests.git`
cd mavlink_support_tests
pip install -r requirements.txt
git clone https://github.com/mavlink/mavlink.git --recursive #note, needed for getting entities for tests, so must be under mavlink support tests
```

you will also need PX4-Autopilot or something to test agasint


To run against PX4 in local simulator:

```
python3 libmav_msg_cmd.py
```


## Files

To list

- 