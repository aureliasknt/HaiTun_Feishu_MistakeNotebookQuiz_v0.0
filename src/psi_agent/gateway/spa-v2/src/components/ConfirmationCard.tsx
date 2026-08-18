import { useState } from "react";
import "./confirmation-card.css";
import {
  answerPendingCard,
  type CardAnswer,
  type PendingCard,
} from "../services/outreachApi";

/**
 * 理解确认卡 —— 场景 3 在工作台里的那一张。
 *
 * 与飞书那张卡**同一张**: 一句提问加三个按钮 (understood / partial / not_understood),
 * 都对齐 ``_outreach_confirm.build_card``, 且共用一个 ``qa_id``。所以在页面上答完,
 * 机器人里那张也随之失效 —— 一次性语义由服务端的 ``qa_id`` 闸门保证, 不靠界面自觉。
 *
 * 卡面不复述问题、答案要点或检验题: 它紧跟在被确认的那条答案后面出现, 复述一遍只会把
 * 按钮挤下去、让人把同样的话读两遍。提问语来自服务端 (``card.prompt``), 因此两处措辞
 * 不会各自漂移。
 */

const BUTTONS: { answer: CardAnswer; label: string; tone: string }[] = [
  { answer: "understood", label: "✅ 懂了", tone: "ok" },
  { answer: "partial", label: "🤔 不太懂", tone: "mid" },
  { answer: "not_understood", label: "❌ 没看懂", tone: "no" },
];

type Props = {
  card: PendingCard;
  /** Called after a click lands, so the shell can drop the card and show the closing line. */
  onAnswered: (closing: string, graduated: boolean) => void;
};

export default function ConfirmationCard({ card, onAnswered }: Props) {
  const [busy, setBusy] = useState<CardAnswer | null>(null);
  const [error, setError] = useState("");

  const answer = async (choice: CardAnswer) => {
    if (busy) return;
    setBusy(choice);
    setError("");
    try {
      const result = await answerPendingCard(card.qaId, choice);
      onAnswered(result.closing, result.graduated);
    } catch (e) {
      // A refusal (stale/duplicate qa_id) must say so — a silently dead card would
      // leave the user clicking a button that never does anything.
      setError(e instanceof Error ? e.message : "作答失败，请重试");
      setBusy(null);
    }
  };

  return (
    <section className="confirm-card" aria-label={card.prompt}>
      <p className="confirm-card-prompt">{card.prompt}</p>
      <div className="confirm-card-actions">
        {BUTTONS.map((button) => (
          <button
            key={button.answer}
            type="button"
            className={`confirm-card-button ${button.tone}`}
            disabled={busy !== null}
            aria-busy={busy === button.answer}
            onClick={() => void answer(button.answer)}
          >
            {button.label}
          </button>
        ))}
      </div>
      {error && (
        <p className="confirm-card-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
