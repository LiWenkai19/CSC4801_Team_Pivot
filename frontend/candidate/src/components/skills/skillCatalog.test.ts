import { expect, test } from "vitest";
import { skillOptions, uniqueSkills } from "./skillCatalog";

test("skills deduplicate casing and whitespace while preserving distinct languages and punctuation", () => {
  expect(uniqueSkills([" JAVA ", "java", "JavaScript", "C++", "C#", "Node.js", "自定义", "  "]))
    .toEqual(["java", "javascript", "c++", "c#", "node.js", "自定义"]);
});

test("each catalog entry has a unique canonical value and Java and JavaScript remain separate", () => {
  const options = skillOptions();
  expect(new Set(options.map(option => option.value)).size).toBe(options.length);
  expect(options.find(option => option.value === "java")?.label).toBe("Java");
  expect(options.find(option => option.value === "javascript")?.label).toBe("JavaScript");
});

test("caller extensions override only the same canonical value, reject blanks and preserve custom labels", () => {
  const options = skillOptions([
    { value: " JAVA ", label: "Java (JVM)" }, { value: " Custom ", label: "自定义" },
    { value: " ", label: "invalid" },
  ]);
  expect(options.filter(option => option.value === "java")).toEqual([{ value: "java", label: "Java (JVM)" }]);
  expect(options.find(option => option.value === "custom")).toEqual({ value: "custom", label: "自定义" });
  expect(options.some(option => !option.value)).toBe(false);
});
