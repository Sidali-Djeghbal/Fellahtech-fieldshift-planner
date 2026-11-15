import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6 text-center">
      <h2 className="text-2xl font-bold text-[#111827]">Page Not Found</h2>
      <p className="mt-2 text-sm text-[#6B7280]">Could not find requested resource</p>
      <Link
        href="/dashboard"
        className="mt-4 rounded-lg bg-[#00291B] px-4 py-2 text-xs font-semibold text-white hover:bg-[#003825] transition"
      >
        Return to Dashboard
      </Link>
    </div>
  );
}
