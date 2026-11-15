import React from "react";

interface LogoProps {
  className?: string;
  size?: number;
  ariaLabel?: string;
}

export const FieldShiftLogo: React.FC<LogoProps> = ({
  className = "w-6 h-8",
  size,
  ariaLabel = "FieldShift",
}) => (
  <svg
    width={size || 24}
    height={size ? (size * 32) / 24 : 32}
    viewBox="0 0 24 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-label={ariaLabel}
  >
    {/* Upper Wing: Slanted Rhombus Facet */}
    <path d="M15 1.5L20 9.5H12L7 1.5H15Z" fill="#5FA87D" />
    <path d="M15 1.5L20 9.5L15 14.5L10 6.5L15 1.5Z" fill="#7BB293" fillOpacity="0.85" />

    {/* Middle Left Dark Emerald Block */}
    <path d="M2.5 11H10.5V17.5H2.5V11Z" fill="#137135" />

    {/* Middle Center Translucent Mint Bridge */}
    <path d="M10.5 11L15 6.5L12 21L7.5 25.5L10.5 11Z" fill="#BCE4C9" fillOpacity="0.7" />

    {/* Middle Right Dark Emerald Block */}
    <path d="M13.5 11H21.5V17.5H13.5V11Z" fill="#137135" />

    {/* Lower Wing: Slanted Rhombus Facet */}
    <path d="M9 30.5L4 22.5H12L17 30.5H9Z" fill="#5FA87D" />
    <path d="M9 30.5L4 22.5L9 17.5L14 25.5L9 30.5Z" fill="#7BB293" fillOpacity="0.85" />
  </svg>
);
