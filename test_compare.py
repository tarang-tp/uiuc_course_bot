import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

import bot


def test_parse_course_id():
    cases = {
        "cs225": "CS 225",
        "CS 225": "CS 225",
        "  math241 ": "MATH 241",
        "ace0240": "ACE 240",
        "225": None,
        "cs": None,
        "cs 225 extra": None,
        "": None,
    }
    ok = True
    for text, expected in cases.items():
        got = bot.parse_course_id(text)
        status = "PASS" if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"{status}: parse_course_id({text!r}) -> {got!r} (expected {expected!r})")
    return ok


def test_fetch_and_embed():
    conn = bot.get_db_connection()
    a = bot.fetch_compare_data(conn, "CS 225")
    b = bot.fetch_compare_data(conn, "MATH 241")
    missing = bot.fetch_compare_data(conn, "ZZZ 999")
    conn.close()

    ok = True
    for label, cond in [
        ("CS 225 found with GPA", a is not None and a['average_gpa'] is not None),
        ("MATH 241 found with GPA", b is not None and b['average_gpa'] is not None),
        ("unknown course returns None", missing is None),
    ]:
        print(f"{'PASS' if cond else 'FAIL'}: {label}")
        ok = ok and cond
    if not ok:
        return False

    embed = bot.build_compare_embed(a, b)
    field_names = [f.name for f in embed.fields]
    for label, cond in [
        ("embed has a field per course", field_names[:2] == ["CS 225", "MATH 241"]),
        ("embed has a verdict", "Verdict" in field_names),
        ("CS 225 verdict names easier course", "CS 225" in embed.fields[-1].value),
        ("field values within Discord limit", all(len(f.value) <= 1024 for f in embed.fields)),
    ]:
        print(f"{'PASS' if cond else 'FAIL'}: {label}")
        ok = ok and cond

    # Tie case and missing-GPA case
    tie = dict(a, average_gpa=b['average_gpa'])
    verdict = bot.build_compare_embed(tie, b).fields[-1].value
    cond = "essentially the same" in verdict
    print(f"{'PASS' if cond else 'FAIL'}: tie verdict")
    ok = ok and cond

    no_gpa = dict(a, average_gpa=None, total_graded=None)
    cond = "Verdict" not in [f.name for f in bot.build_compare_embed(no_gpa, b).fields]
    print(f"{'PASS' if cond else 'FAIL'}: no verdict when GPA missing")
    return ok and cond


def make_interaction():
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


def test_command_paths():
    cb = bot.compare_command.callback
    ok = True

    async def run():
        nonlocal ok
        # Invalid format
        i = make_interaction()
        await cb(i, "cs", "math241")
        c = i.response.send_message.await_args.kwargs.get("ephemeral") is True
        print(f"{'PASS' if c else 'FAIL'}: invalid format rejected ephemerally")
        ok = ok and c

        # Same course twice (different spellings)
        i = make_interaction()
        await cb(i, "cs225", "CS 225")
        c = i.response.send_message.await_args.kwargs.get("ephemeral") is True
        print(f"{'PASS' if c else 'FAIL'}: duplicate course rejected")
        ok = ok and c

        # Unknown course
        i = make_interaction()
        await cb(i, "cs225", "zzz999")
        msg = i.followup.send.await_args.args[0]
        c = "ZZZ 999" in msg and "CS 225" not in msg
        print(f"{'PASS' if c else 'FAIL'}: unknown course reported only ({msg})")
        ok = ok and c

        # Happy path
        i = make_interaction()
        await cb(i, "cs225", "math241")
        c = "embed" in i.followup.send.await_args.kwargs
        print(f"{'PASS' if c else 'FAIL'}: happy path sends embed")
        ok = ok and c

    asyncio.run(run())
    return ok


if __name__ == "__main__":
    if not os.path.exists(bot.DB_NAME):
        print(f"Error: {bot.DB_NAME} does not exist. Run build_db.py first.")
        raise SystemExit(1)
    results = [test_parse_course_id(), test_fetch_and_embed(), test_command_paths()]
    if all(results):
        print("\nAll /compare tests PASSED successfully!")
    else:
        print("\nSome tests FAILED.")
        raise SystemExit(1)
