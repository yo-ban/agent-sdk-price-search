import { useState } from "react";
import type { SearchFormValues } from "../types";

interface Props {
  onSubmit: (values: SearchFormValues) => Promise<void> | void;
  isSubmitting?: boolean;
}

export function SearchForm({ onSubmit, isSubmitting = false }: Props) {
  const [productNameAndModelNumber, setProductNameAndModelNumber] = useState("");
  const [color, setColor] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [market, setMarket] = useState("JP");
  const [currency, setCurrency] = useState("JPY");
  const [maxOffers, setMaxOffers] = useState(3);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      productNameAndModelNumber,
      color,
      manufacturer,
      market,
      currency,
      maxOffers,
    });
  };

  return (
    <>
      <div className="search-hero">
        <h1>商品の価格を調べる</h1>
        <p>複数の店舗を自動比較し、調査の過程と結果を確認できます</p>
      </div>
      <form className="search-form" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="productNameAndModelNumber">商品名 / 型番</label>
          <input
            id="productNameAndModelNumber"
            type="text"
            placeholder=""
            value={productNameAndModelNumber}
            onChange={(e) => setProductNameAndModelNumber(e.target.value)}
            required
          />
        </div>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="color">カラー</label>
            <input
              id="color"
              type="text"
              placeholder="任意"
              value={color}
              onChange={(e) => setColor(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label htmlFor="manufacturer">メーカー</label>
            <input
              id="manufacturer"
              type="text"
              placeholder="任意"
              value={manufacturer}
              onChange={(e) => setManufacturer(e.target.value)}
            />
          </div>
        </div>
        <div className="form-divider" aria-hidden="true" />
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="market">市場</label>
            <select
              id="market"
              value={market}
              onChange={(e) => setMarket(e.target.value)}
            >
              <option value="JP">日本 (JP)</option>
              <option value="US">US</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="currency">通貨</label>
            <select
              id="currency"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
            >
              <option value="JPY">JPY</option>
              <option value="USD">USD</option>
            </select>
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="maxOffers">最大比較件数</label>
          <select
            id="maxOffers"
            value={maxOffers}
            onChange={(e) => setMaxOffers(Number(e.target.value))}
          >
            <option value={1}>1件</option>
            <option value={3}>3件</option>
            <option value={5}>5件</option>
          </select>
        </div>
        <button type="submit" className="btn-primary" disabled={isSubmitting}>
          {isSubmitting ? "調査を開始しています..." : "価格を調査する"}
        </button>
      </form>
    </>
  );
}
