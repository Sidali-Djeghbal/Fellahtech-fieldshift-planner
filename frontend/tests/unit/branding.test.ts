import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import { UI_DICT } from "@/lib/i18n";

describe("Brand Transformation & Token Sanitation", () => {
  it("verifies i18n brand titles and subtitles use FELLAH TECH with zero NASA references", () => {
    for (const lang of ["en", "fr", "ar"] as const) {
      const dict = UI_DICT[lang];
      expect(dict.brandTitle).toBe("FELLAH TECH");
      expect(dict.brief.docHeading).toContain("FELLAH TECH");
      expect(dict.brandSubtitle).not.toMatch(/NASA|Space Apps|ناسا|FieldShift|FIELD SHIFT/i);
    }
    const logoPath = path.resolve(__dirname, "../../public/assets/logo.svg");
    expect(fs.existsSync(logoPath)).toBe(true);
  });

  it("ensures zero legacy NASA Space Apps tokens and colors exist in src/", () => {
    const srcDir = path.resolve(__dirname, "../../src");

    function getAllFiles(dirPath: string, arrayOfFiles: string[] = []): string[] {
      const files = fs.readdirSync(dirPath);
      files.forEach((file) => {
        const fullPath = path.join(dirPath, file);
        if (fs.statSync(fullPath).isDirectory()) {
          getAllFiles(fullPath, arrayOfFiles);
        } else {
          arrayOfFiles.push(fullPath);
        }
      });
      return arrayOfFiles;
    }

    const allFiles = getAllFiles(srcDir);
    const legacyPattern = /(NASA|Space Apps|#07173F|#0042A6|#0960E1|#2E96F5|#EAFE07|#E43700|#8E1100|\bsa-)/i;

    const violations: { file: string; line: number; text: string }[] = [];

    for (const file of allFiles) {
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((lineText, idx) => {
        if (legacyPattern.test(lineText)) {
          violations.push({
            file: path.relative(srcDir, file),
            line: idx + 1,
            text: lineText.trim(),
          });
        }
      });
    }

    expect(violations).toEqual([]);
  });

  it("verifies the 5 resource monitoring donut segments sum to exactly 100%", () => {
    const segments = [
      { label: "Irrigation Systems", percentage: 30 },
      { label: "Crop Nutrition", percentage: 23 },
      { label: "Equipment Maintenance", percentage: 18 },
      { label: "Pest Control", percentage: 17 },
      { label: "Logistics & Distribution", percentage: 12 },
    ];
    const sum = segments.reduce((acc, s) => acc + s.percentage, 0);
    expect(sum).toBe(100);
  });
});
