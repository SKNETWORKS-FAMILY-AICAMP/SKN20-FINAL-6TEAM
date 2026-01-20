"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  User,
  Table,
  Bell,
  LogIn,
  UserPlus,
  Menu,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface SidebarProps {
  className?: string;
}

const mainNavItems = [
  {
    title: "dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    title: "profile",
    href: "/dashboard/profile",
    icon: User,
  },
  {
    title: "tables",
    href: "/dashboard/tables",
    icon: Table,
  },
  {
    title: "notifications",
    href: "/dashboard/notifications",
    icon: Bell,
  },
];

const authNavItems = [
  {
    title: "sign in",
    href: "/auth/sign-in",
    icon: LogIn,
  },
  {
    title: "sign up",
    href: "/auth/sign-up",
    icon: UserPlus,
  },
];

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <>
      {/* Mobile menu button */}
      <Button
        variant="ghost"
        size="icon"
        className="fixed left-4 top-4 z-50 lg:hidden"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
      </Button>

      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col bg-gray-900 text-white transition-transform lg:translate-x-0",
          isOpen ? "translate-x-0" : "-translate-x-full",
          className
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center gap-2 border-b border-gray-800 px-6">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-white">
            <span className="text-sm font-bold text-gray-900">M</span>
          </div>
          <Link href="/dashboard" className="text-sm font-semibold">
            Material Tailwind React
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-4">
          <ul className="space-y-1">
            {mainNavItems.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href === "/dashboard" && pathname === "/dashboard");
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={() => setIsOpen(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-white/10 text-white"
                        : "text-gray-400 hover:bg-white/5 hover:text-white"
                    )}
                  >
                    <item.icon className="h-5 w-5" />
                    {item.title}
                  </Link>
                </li>
              );
            })}
          </ul>

          <div className="mt-6">
            <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
              auth pages
            </p>
            <ul className="space-y-1">
              {authNavItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={() => setIsOpen(false)}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                        isActive
                          ? "bg-white/10 text-white"
                          : "text-gray-400 hover:bg-white/5 hover:text-white"
                      )}
                    >
                      <item.icon className="h-5 w-5" />
                      {item.title}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        </nav>
      </aside>
    </>
  );
}
