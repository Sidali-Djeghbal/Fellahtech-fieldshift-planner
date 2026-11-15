export function canUseWebgl(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(
      canvas.getContext("webgl2", { failIfMajorPerformanceCaveat: false }) ||
        canvas.getContext("webgl", { failIfMajorPerformanceCaveat: false })
    );
  } catch {
    return false;
  }
}

