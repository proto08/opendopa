import pytest

from opendopa_pipeline import gate


class TestExtractNumbers:
    def test_comma_fullwidth_and_datetime(self):
        assert gate.extract_numbers("1,234件") == ["1234"]
        assert gate.extract_numbers("１２３４件") == ["1234"]
        assert gate.extract_numbers("2022年12月6日11時20分") == ["2022", "12", "6", "11", "20"]

    def test_decimal_and_leading_zero(self):
        assert gate.extract_numbers("1.50%") == ["1.5"]
        assert gate.extract_numbers("007号") == ["7"]

    def test_kanji_numerals_only_before_counters(self):
        assert gate.extract_numbers("三十二人が負傷") == ["32"]
        assert gate.extract_numbers("二〇二二年") == ["2022"]
        assert gate.extract_numbers("一部が破損し、万一に備える") == []

    @pytest.mark.parametrize(
        ("text", "n"), [("三十二", 32), ("百五", 105), ("十", 10), ("二〇", 20)]
    )
    def test_kanji_to_int(self, text, n):
        assert gate.kanji_to_int(text) == n


class TestUnreplaced:
    def test_pass_and_fail(self):
        assert gate.check_unreplaced(["東京都で報告されました。"]) == []
        assert gate.check_unreplaced(["{place}で報告されました。"])
        assert gate.check_unreplaced(["閉じていない}"])


class TestNumbers:
    ROW = {"date": "2022年12月6日11時20分", "OCCURRENCE_DATE": "2022/12/6 11:20", "No.": 7}
    NUMS = [{"name": "pref_seq", "value": 3, "display": "3件", "inputs": {"pref": "東京都"}}]

    def test_match_with_row_and_numbers(self):
        lines = ["2022年12月6日11時20分、東京都で3件目。第7号。"]
        assert gate.check_numbers(lines, self.ROW, self.NUMS) == []

    def test_fullwidth_and_comma_normalized(self):
        row = {"V": 1234}
        assert gate.check_numbers(["１,２３４件"], row) == []
        assert gate.check_numbers(["1,234件"], {"V": "１２３４"}) == []

    def test_mismatch(self):
        errs = gate.check_numbers(["報告は99件です。"], self.ROW, self.NUMS)
        assert errs == ["元データにない数字: 99"]

    def test_numbers_display_allows_rounded_money(self):
        nums = [{"value": 2008428041000, "display": "約2兆円", "inputs": {}}]
        assert gate.check_numbers(["売上は約2兆円です。"], {}, nums) == []


def test_required():
    assert gate.check_required(["A", "B"], {"A": "x", "B": None}) == ["必須の列が空: B"]
    assert gate.check_required(["A"], {"A": float("nan")})
    assert gate.check_required(["A"], {"A": "x"}) == []


class TestLength:
    @pytest.mark.parametrize("sec", [15.0, 22.5, 30.0])
    def test_in_range(self, sec):
        assert gate.check_length(sec) == []

    @pytest.mark.parametrize("sec", [14.0, 30.5])
    def test_out_of_range(self, sec):
        assert gate.check_length(sec)


class TestPii:
    @pytest.mark.parametrize(
        "text",
        [
            "連絡先は03-1234-5678です。",
            "09012345678に連絡した。",
            "a.b@example.com に送った。",
            "東京都港区3丁目で発生。",
            "山田太郎氏が操縦していた。",
            "〒100-0001 東京",
        ],
    )
    def test_detects(self, text):
        assert gate.check_pii([text])

    def test_clean(self):
        assert gate.check_pii(["東京都港区で、無人航空機が建物に接触しました。同氏は無事。"]) == []


class TestForbidden:
    @pytest.mark.parametrize("w", ["原因は風です。", "操縦者の責任は重い。", "強風のせいで墜落"])
    def test_detects(self, w):
        assert gate.check_forbidden([w])

    def test_clean(self):
        assert gate.check_forbidden(["強風の中で墜落したと記載されています。"]) == []


def test_duplicates():
    assert gate.check_duplicates(["a", "b", "a", None, None, "b"]) == [
        False,
        False,
        True,
        False,
        False,
        True,
    ]
    assert gate.script_text_key(["a b", "c"]) == gate.script_text_key(["ab", " c"])


class TestCasualtyDetail:
    @pytest.mark.parametrize(
        "text",
        [
            "プロペラが補助者の足の甲に接触し負傷した。",
            "操縦者が顔面及び右腕を負傷した。",
            "機体が操縦者の左手に接触した。",
            "補助者が手を伸ばし、プロペラに接触したことで負傷した。",
            "プロペラの接触で右手背部を負傷した。",
            "プロペラは直接皮膚に接触していないが、打撲を負った。",
        ],
    )
    def test_detects(self, text):
        assert gate.check_casualty_detail(["事故が報告されました。", text])

    @pytest.mark.parametrize(
        "text",
        [
            "負傷者の報告があります。",
            "機体の被害は、腕部固定金具の破損と記載されています。",
            "機首部・主翼の損傷と記載されています。",
            "事前の周辺確認不足により、近隣家屋に接触し、壁面を損傷させた。",
            "操縦者が足元に気を取られ機体から目を離したことで電線に接触した。",
            "操縦者の指が送信機に触れたことで機体が動き、窓ガラスに接触した。",
            "運転手に接触して車両が破損した。",
            "補助者が指示を誤り、機体が建物に接触した。",
        ],
    )
    def test_clean(self, text):
        assert gate.check_casualty_detail([text]) == []

    def test_check_all_reports_it(self):
        out = gate.check_all(
            lines=["操縦者の右肘に接触し負傷した。"],
            duration_sec=20.0,
            row={},
            numbers=[],
            required=[],
        )
        assert list(out) == ["casualty_detail"]

    def test_check_all_checks_extra_texts(self):
        # 見出し・チップ・コメントなど字幕以外の表示文も検査する
        out = gate.check_all(
            lines=["負傷者の報告があります。"],
            duration_sec=20.0,
            row={},
            numbers=[],
            required=[],
            extra_texts=["操縦者の右肘に接触し負傷した。"],
        )
        assert list(out) == ["casualty_detail"]


def test_decision_flags():
    decs = {"pii": {"excluded": True}, "template": {"choice": "other"}}
    assert gate.check_decisions(decs) == ["判断 pii で除外"]


def test_check_all_collects_failures():
    out = gate.check_all(
        lines=["{x}で99件。原因は不明。"],
        duration_sec=5.0,
        row={"A": None},
        numbers=[],
        required=["A"],
    )
    assert list(out) == ["missing", "unreplaced", "number_mismatch", "length", "forbidden"]


def test_summarize():
    assert gate.summarize([20, 30, 25]) == {"min": 20, "median": 25, "max": 30}
    assert gate.summarize([])["min"] is None
