from hosoai.sources.quality import fee_problem


def test_broken_fee_boxes_are_detected() -> None:
    # real broken texts from official pages (id-card-reissue, household-business, tạm trú)
    assert fee_problem("Phí: Trực tiếp Trực tuyến\nLệ phí: 07 Ngày làm việc\nChưa quy định.")
    assert fee_problem("Lệ phí: Trực tiếp - 3 Ngày làm việc\nPhí: Trực tuyến - 3 Ngày làm việc")
    assert fee_problem("Phí: 1\nLệ phí: Không")


def test_real_fees_are_kept() -> None:
    assert fee_problem("Phí: Không\nLệ phí: Không") is None
    assert fee_problem("Phí: 160.000/hộ chiếu\nLệ phí: Không") is None
    assert fee_problem("Phí: 10 USD\nLệ phí: Không") is None
    # per-method table: has processing days but also real amounts
    assert (
        fee_problem(
            "Phí: Trực tiếp 07 Ngày làm việc20.000Trường hợp công dân nộp hồ sơ trực tiếp "
            "thu 20.000 đồng/lần đăng ký\nLệ phí: Không"
        )
        is None
    )
