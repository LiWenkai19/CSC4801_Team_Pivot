export function RecommendationScore({ score }: { score: number }) {
  return <span className="score" aria-label={`占位匹配分数 ${score}，算法待开发`}>
    {score} 分（占位）
  </span>;
}
