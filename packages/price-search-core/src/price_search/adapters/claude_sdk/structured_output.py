"""Infrastructure layer: Claude 構造化出力の schema と DTO 変換。"""

from __future__ import annotations

from typing import Any

from price_search.ports.price_research_agent_port import (
    RawIdentifiedProduct,
    RawOfferResult,
)


def build_structured_output_schema() -> dict[str, Any]:
    """エージェントに期待する構造化出力の JSON Schema を返す。"""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["identified_product", "summary", "offers"],
        "properties": {
            "identified_product": {
                "type": "object",
                "description": "The single product determined as the research target.",
                "additionalProperties": False,
                "required": [
                    "name",
                    "model_number",
                    "manufacturer",
                    "product_url",
                    "release_date",
                    "is_substitute",
                    "substitution_reason",
                ],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Official product name as identified during research.",
                    },
                    "model_number": {
                        "type": "string",
                        "description": "Manufacturer model or part number. Empty string if unknown.",
                    },
                    "manufacturer": {
                        "type": "string",
                        "description": "Manufacturer or brand name. Empty string if unknown.",
                    },
                    "product_url": {
                        "type": "string",
                        "description": (
                            "URL of the manufacturer's official product page for the identified product. Empty string if none found."
                        ),
                    },
                    "release_date": {
                        "type": "string",
                        "description": (
                            "Original release or launch date in ISO-8601 format. "
                            "Empty string if not confirmed."
                        ),
                    },
                    "is_substitute": {
                        "type": "boolean",
                        "description": (
                            "True when the returned identified product is not the exact requested "
                            "target, including variant substitutions and successor/equivalent substitutions."
                        ),
                    },
                    "substitution_reason": {
                        "type": "string",
                        "description": (
                            "Japanese-language one-sentence explanation of why the exact requested target could not be used "
                            "and what substitute product or variant was selected instead. "
                            "Empty string when is_substitute is false."
                        ),
                    },
                },
            },
            "summary": {
                "type": "string",
                "description": (
                    "Japanese-language summary of the price research. "
                    "Briefly explain the low-end price band and any caveats."
                ),
            },
            "offers": {
                "type": "array",
                "description": "One entry per merchant listing verified via browser.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "merchant_name",
                        "merchant_product_name",
                        "merchant_product_url",
                        "currency",
                        "item_price",
                        "availability",
                        "evidence",
                    ],
                    "properties": {
                        "merchant_name": {
                            "type": "string",
                            "description": "Name of the merchant or retailer.",
                        },
                        "merchant_product_name": {
                            "type": "string",
                            "description": "Product name as shown on the merchant page.",
                        },
                        "merchant_product_url": {
                            "type": "string",
                            "description": (
                                "URL of the specific purchase page on the merchant's own site where the price in item_price is displayed. "
                                "Must be a page you actually visited and confirmed shows that price. Do not use aggregator or price-comparison pages."
                            ),
                        },
                        "currency": {
                            "type": "string",
                            "description": "ISO-4217 currency code of the listed price.",
                        },
                        "item_price": {
                            "type": "number",
                            "description": "Numeric price in the listed currency.",
                        },
                        "availability": {
                            "type": "string",
                            "description": (
                                "Stock status as shown on the page "
                                "(e.g. in_stock, backorder, out_of_stock)."
                            ),
                        },
                        "evidence": {
                            "type": "string",
                            "description": "One sentence citing the key facts from the merchant page.",
                        },
                    },
                },
            },
        },
    }


def raw_identified_product_from_payload(payload: dict[str, Any]) -> RawIdentifiedProduct:
    """構造化 JSON の identified_product をポート層の DTO に変換する。"""
    return RawIdentifiedProduct(
        name=str(payload.get("name") or "").strip(),
        model_number=str(payload.get("model_number") or "").strip(),
        manufacturer=str(payload.get("manufacturer") or "").strip(),
        product_url=str(payload.get("product_url") or "").strip(),
        release_date=str(payload.get("release_date") or "").strip(),
        is_substitute=bool(payload.get("is_substitute", False)),
        substitution_reason=str(payload.get("substitution_reason") or "").strip(),
    )


def raw_offer_from_payload(payload: dict[str, Any]) -> RawOfferResult:
    """構造化 JSON ペイロードをポート層の生 DTO に変換する。"""
    return RawOfferResult(
        merchant_name=str(payload["merchant_name"]).strip(),
        merchant_product_name=str(payload["merchant_product_name"]).strip(),
        merchant_product_url=str(payload["merchant_product_url"]).strip(),
        currency=str(payload["currency"]).strip(),
        item_price=float(payload["item_price"]),
        availability=str(payload["availability"]).strip(),
        evidence=str(payload["evidence"]).strip(),
    )
