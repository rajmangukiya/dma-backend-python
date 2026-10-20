import time

from src.database.base import new_id


def test_new_id_is_uuid_v7() -> None:
    value = new_id()

    assert value.version == 7
    assert value.variant == "specified in RFC 4122"  # the RFC 9562 variant bits (10)


def test_new_ids_sort_in_creation_order() -> None:
    earlier = new_id()
    time.sleep(0.002)  # ids within the same millisecond have no guaranteed order
    later = new_id()

    assert earlier < later
    assert len({new_id() for _ in range(1000)}) == 1000
