"""Domain tests for offer normalization and ranking."""

from decimal import Decimal

from price_search.domain.models import IdentifiedProduct, PriceOffer, ProductResearchQuery
from price_search.domain.services import build_report

_DUMMY_PRODUCT = IdentifiedProduct(
    name="Test Product",
    model_number="TP-001",
    manufacturer="TestCo",
    product_url="",
    release_date="",
    is_substitute=False,
    substitution_reason="",
)


def test_build_report_ranks_target_currency_offers_first() -> None:
    """JPY offers should be ranked before non-JPY offers when prices are compared."""
    query = ProductResearchQuery(
        product_name="PlayStation 5 Pro",
        market="JP",
        currency="JPY",
        max_offers=3,
    )
    non_target_offer = PriceOffer(
            merchant_name="Store B",
            merchant_product_name="PS5 Pro",
            merchant_product_url="https://example.com/b",
            currency="USD",
            item_price=Decimal("699"),
            availability="在庫あり",
            evidence="USD listing",
        )
    target_offer = PriceOffer(
            merchant_name="Store A",
            merchant_product_name="PS5 Pro",
            merchant_product_url="https://example.com/a",
            currency="JPY",
            item_price=Decimal("119800"),
            availability="在庫あり",
            evidence="JPY listing",
        )
    offers = [non_target_offer, target_offer]

    report = build_report(
        query=query,
        identified_product=_DUMMY_PRODUCT,
        summary="summary",
        offers=offers,
    )

    assert report.offers[0] is target_offer


def test_build_report_deduplicates_by_merchant_and_url_using_lower_price() -> None:
    """Duplicate merchant/url pairs should keep only the cheaper observation."""
    query = ProductResearchQuery(
        product_name="MacBook Air",
        market="JP",
        currency="JPY",
        max_offers=3,
    )
    expensive_offer = PriceOffer(
            merchant_name="Apple",
            merchant_product_name="MacBook Air",
            merchant_product_url="https://example.com/apple",
            currency="JPY",
            item_price=Decimal("164800"),
            availability="在庫あり",
            evidence="first",
        )
    cheaper_offer = PriceOffer(
            merchant_name="Apple",
            merchant_product_name="MacBook Air",
            merchant_product_url="https://example.com/apple",
            currency="JPY",
            item_price=Decimal("159800"),
            availability="在庫あり",
            evidence="second",
        )
    offers = [expensive_offer, cheaper_offer]

    report = build_report(
        query=query,
        identified_product=_DUMMY_PRODUCT,
        summary="summary",
        offers=offers,
    )

    assert len(report.offers) == 1
    assert report.offers[0] is cheaper_offer
