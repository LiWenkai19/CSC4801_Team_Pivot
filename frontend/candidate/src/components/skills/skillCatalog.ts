// value 是保存和比较用的规范值；label 是展示给用户看的名称。
export type SkillOption = { value: string; label: string };

// trim 去掉首尾空格，toLowerCase 让 Python 和 python 按同一技能比较。
export const normalizeSkill = (value: string) => value.trim().toLowerCase();

// 先规范化并过滤空值，再用 Set 去重，最后转回普通数组。
export const uniqueSkills = (values: readonly string[]) =>
  [...new Set(values.map(normalizeSkill).filter(Boolean))];

// 预设建议只是搜索目录；用户仍可在选择器中添加自己的技能。
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
  // Map 按规范 value 存储，合并外部选项时同一个技能只保留一项。
  const options = new Map<string, SkillOption>();
  for (const option of [...defaultSkillOptions, ...extra]) {
    const value = normalizeSkill(option.value);
    if (value) options.set(value, { value, label: option.label.trim() || value });
  }
  return [...options.values()];
}
