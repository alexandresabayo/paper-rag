export const scenarioCaptions = {
  database_only: "database only · high retrieval confidence",
  hybrid: "hybrid · retrieval + general knowledge",
  model_first: "model-led · limited retrieval match",
  model_only: "model only · no relevant match found",
};

export function scenarioCaption(scenario, answerMode) {
  if (answerMode === "direct_model") return "direct model · no retrieval";
  return scenarioCaptions[scenario] || "";
}
