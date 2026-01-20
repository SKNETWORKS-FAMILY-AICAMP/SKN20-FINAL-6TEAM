"use client";

import * as React from "react";
import Link from "next/link";
import { Search, Settings, Bell, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface HeaderProps {
  breadcrumb: {
    parent: string;
    current: string;
  };
}

export function Header({ breadcrumb }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60 lg:px-6">
      <div>
        <nav className="flex items-center gap-1 text-sm text-muted-foreground">
          <Link href="/dashboard" className="hover:text-foreground">
            {breadcrumb.parent}
          </Link>
          <span>/</span>
          <span className="text-foreground">{breadcrumb.current}</span>
        </nav>
        <h1 className="text-lg font-semibold">{breadcrumb.current}</h1>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search"
            className="w-64 pl-9"
          />
        </div>
        <Button variant="ghost" size="icon" className="md:hidden">
          <Search className="h-5 w-5" />
        </Button>
        <Link href="/auth/sign-in">
          <Button variant="ghost" size="icon">
            <User className="h-5 w-5" />
          </Button>
        </Link>
        <Button variant="ghost" size="icon">
          <Settings className="h-5 w-5" />
        </Button>
        <Button variant="ghost" size="icon">
          <Bell className="h-5 w-5" />
        </Button>
      </div>
    </header>
  );
}
