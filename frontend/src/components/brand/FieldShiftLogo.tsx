import React from "react";

interface LogoProps {
  className?: string;
  size?: number;
  ariaLabel?: string;
}

export const FieldShiftLogo: React.FC<LogoProps> = ({
  className = "",
  size = 30,
  ariaLabel = "FELLAH TECH",
}) => (
  <span
    className={`inline-flex shrink-0 items-center justify-center rounded-full bg-white p-[1.5px] shadow-[0_1px_4px_rgba(0,0,0,0.12)] ring-1 ring-[#16a637]/20 dark:bg-white/95 dark:ring-white/25 ${className}`.trim()}
    style={{ width: size, height: size }}
  >
    <img
      src="/assets/logo.svg"
      alt={ariaLabel}
      width={size}
      height={size}
      className="h-full w-full rounded-full object-contain"
    />
  </span>
);

export const FellahTechLogo = FieldShiftLogo;
