"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  SquaresFour,
  Plant,
  CloudSun,
  FileText,
  Users,
  MapTrifold,
  ChartBar,
  Gear,
  Info,
  Moon,
  ArrowLeft,
} from "@phosphor-icons/react";
import { FieldShiftLogo } from "./FieldShiftLogo";
import { useAppStore } from "@/store/useAppStore";

interface NavigationSidebarProps {
  onOpenAuth?: () => void;
  onLogout?: () => void;
}

export function NavigationSidebar({ onOpenAuth, onLogout }: NavigationSidebarProps) {
  const pathname = usePathname();
  const { user, authMode, plainMode, togglePlainMode } = useAppStore();

  const navItems = [
    { href: "/", label: "Command Center", icon: SquaresFour },
    { href: "/farm-profile", label: "Crop Management", icon: Plant },
    { href: "/weather", label: "Climate & Weather", icon: CloudSun, isMock: true },
    { href: "/evidence", label: "Evidence & Reports", icon: FileText },
    { href: "/community", label: "Community & Team", icon: Users, isMock: true },
    { href: "/select-field", label: "Field Boundary", icon: MapTrifold },
    { href: "/comparison", label: "Rotation Analytics", icon: ChartBar },
  ];

  return (
    <aside
      aria-label="Sidebar navigation"
      className="no-print fixed top-0 bottom-0 left-0 z-40 flex w-[60px] flex-col items-center bg-white border-r border-[#E5E7EB] py-4 select-none"
    >
      {/* Brand Logo at Top */}
      <div className="flex h-12 w-full items-center justify-center pt-1">
        <Link href="/" title="FieldShift Command Center" className="flex items-center justify-center">
          <FieldShiftLogo size={22} className="w-[22px] h-[30px]" />
        </Link>
      </div>

      {/* Subtle Divider below logo */}
      <div className="my-2.5 h-px w-8 bg-[#E5E7EB]" />

      {/* Navigation Icons Stack */}
      <nav aria-label="Main Navigation" className="flex flex-col items-center space-y-2.5 w-full">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;

          if (item.isMock) {
            return (
              <button
                key={item.label}
                type="button"
                title={item.label}
                onClick={() => {}}
                className="group relative flex h-9 w-9 items-center justify-center rounded-xl text-[#374151] hover:bg-gray-100 hover:text-[#111827] transition"
              >
                <Icon size={20} weight="regular" />
                <span className="pointer-events-none absolute left-full ml-2 hidden rounded-md bg-gray-900 px-2 py-1 text-[11px] font-medium text-white shadow group-hover:block z-50 whitespace-nowrap">
                  {item.label}
                </span>
              </button>
            );
          }

          return (
            <Link
              key={item.href}
              href={item.href}
              title={item.label}
              className={`group relative flex items-center justify-center transition ${
                isActive
                  ? "h-9 w-9 rounded-full bg-[#00291B] text-[#84E875] shadow-sm"
                  : "h-9 w-9 rounded-xl text-[#374151] hover:bg-gray-100 hover:text-[#111827]"
              }`}
            >
              <Icon
                size={isActive ? 18 : 20}
                weight={isActive ? "fill" : "regular"}
                className={isActive ? "text-[#84E875]" : "text-[#374151]"}
              />
              <span className="pointer-events-none absolute left-full ml-2 hidden rounded-md bg-gray-900 px-2 py-1 text-[11px] font-medium text-white shadow group-hover:block z-50 whitespace-nowrap">
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>

      {/* Divider */}
      <div className="my-2.5 h-px w-8 bg-[#E5E7EB]" />

      {/* Utility Icons */}
      <div className="flex flex-col items-center space-y-2 w-full">
        <button
          type="button"
          title="Settings"
          className="group relative flex h-8 w-8 items-center justify-center rounded-lg text-[#374151] hover:bg-gray-100 hover:text-[#111827] transition"
        >
          <Gear size={19} weight="regular" />
          <span className="pointer-events-none absolute left-full ml-2 hidden rounded-md bg-gray-900 px-2 py-1 text-[11px] font-medium text-white shadow group-hover:block z-50 whitespace-nowrap">
            Settings
          </span>
        </button>
        <button
          type="button"
          title="Help & About"
          className="group relative flex h-8 w-8 items-center justify-center rounded-lg text-[#374151] hover:bg-gray-100 hover:text-[#111827] transition"
        >
          <Info size={19} weight="regular" />
          <span className="pointer-events-none absolute left-full ml-2 hidden rounded-md bg-gray-900 px-2 py-1 text-[11px] font-medium text-white shadow group-hover:block z-50 whitespace-nowrap">
            About FieldShift
          </span>
        </button>
      </div>

      {/* Vertical Spacer */}
      <div className="flex-1" />

      {/* Footer Controls */}
      <div className="flex flex-col items-center space-y-3 pb-1 w-full">
        {/* Dark / Light Toggle */}
        <button
          type="button"
          title="Toggle Theme"
          onClick={togglePlainMode}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-[#374151] hover:bg-gray-100 hover:text-[#111827] transition"
        >
          <Moon size={18} weight={plainMode ? "fill" : "regular"} />
        </button>

        {/* Logout / Exit Action button */}
        <button
          type="button"
          title={authMode === "none" ? "Guest Mode" : "Logout"}
          onClick={onLogout || onOpenAuth}
          className="flex h-6 w-6 items-center justify-center rounded-full bg-[#EF4444] text-white shadow-sm hover:brightness-110 transition"
        >
          <ArrowLeft size={13} weight="bold" />
        </button>

        {/* User Profile Avatar */}
        <button
          type="button"
          title={user?.full_name ?? "Agricultural Operator"}
          onClick={onOpenAuth}
          className="relative flex h-8 w-8 items-center justify-center rounded-full bg-[#137135] text-white ring-2 ring-white shadow-sm overflow-hidden"
        >
          {/* Avatar representation: SVG avatar representing agricultural operator */}
          <svg viewBox="0 0 32 32" className="h-full w-full">
            <rect width="32" height="32" fill="#137135" />
            <circle cx="16" cy="12" r="6" fill="#FDE68A" />
            <path d="M7 28 C7 21, 11 19, 16 19 C21 19, 25 21, 25 28 Z" fill="#00291B" />
          </svg>
        </button>
      </div>
    </aside>
  );
}
