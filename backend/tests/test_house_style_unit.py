from house_style import EDITORIAL_POLICY, follows_house_style, remove_em_dashes


def test_policy_protects_wording_and_bans_em_dashes():
    lowered = EDITORIAL_POLICY.lower()
    assert "preserve the author's wording" in lowered
    assert "substantive changes" in lowered
    assert "never use an em dash" in lowered


def test_generated_text_cannot_retain_em_dash():
    cleaned = remove_em_dashes("First thought\u2014second thought")
    assert cleaned == "First thought;second thought"
    assert follows_house_style(cleaned)


def test_house_style_validator_rejects_em_dash():
    assert not follows_house_style("This\u2014that")
    assert follows_house_style("This; that")
