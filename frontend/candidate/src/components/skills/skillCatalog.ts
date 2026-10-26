export type SkillOption = { value: string; label: string };

export const normalizeSkill = (value: string) => value.trim().toLowerCase();

export const uniqueSkills = (values: readonly string[]) =>
  [...new Set(values.map(normalizeSkill).filter(Boolean))];

export const defaultSkillOptions: readonly SkillOption[] = [
  "Java", "JavaScript", "TypeScript", "Python", "C", "C++", "C#", "Go", "Rust",
  "Kotlin", "Swift", "PHP", "Ruby", "R", "SQL", "HTML", "CSS", "React", "Vue",
  "Angular", "Node.js", "Spring Boot", "Django", "FastAPI", "Flask", ".NET",
  "MySQL", "PostgreSQL", "SQLite", "MongoDB", "Redis", "Git", "Docker",
  "Kubernetes", "Linux", "AWS", "Azure", "Google Cloud", "REST API", "GraphQL",
  "Jest", "JUnit", "JSON", "JWT", "PyTorch", "TensorFlow", "Machine Learning",
  "Data Analysis", "Figma", "Excel",
].map(label => ({ label, value: normalizeSkill(label) }));

export function skillOptions(extra: readonly SkillOption[] = []): SkillOption[] {
  const options = new Map<string, SkillOption>();
  for (const option of [...defaultSkillOptions, ...extra]) {
    const value = normalizeSkill(option.value);
    if (value) options.set(value, { value, label: option.label.trim() || value });
  }
  return [...options.values()];
}
