# Nutrition & Recommendation Grounding

Approved, safe-to-recommend categories only (guardrails doc §1, §5, §6):

## Approved food/nutrient recommendations
- Whole-food magnesium sources: spinach (157mg/200g), pumpkin seeds, almonds, black beans.
- Whole-food iron sources: spinach, lentils, red meat (lean cuts), fortified cereal.
- Whole-food B12 sources: eggs, dairy, fortified nutritional yeast (for vegetarians/vegans).
- Sodium-reduction swaps: fresh herbs/spices instead of salt, rinsing canned beans, low-sodium broth.

## Safe recommendation bounds
- Calorie targets: never below 1200/day or above 3000/day for an average adult.
- Exercise targets: never above 150 minutes/week for an average, non-athlete user.
- No unproven supplements, MLM products, or extreme diets (carnivore/zero-carb/extended
  fasting) without explicit medical sign-off.

## Budget-conscious substitutions (avoid socioeconomic bias)
- Prefer whole foods over paid supplements when the user is flagged budget-conscious.
- Example: "spinach instead of a magnesium supplement" rather than "buy XYZ supplement."
