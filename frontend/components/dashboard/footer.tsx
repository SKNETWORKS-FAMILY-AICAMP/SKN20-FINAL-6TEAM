import * as React from "react";
import Link from "next/link";
import { Heart } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t bg-background py-6">
      <div className="container flex flex-col items-center justify-between gap-4 md:flex-row">
        <p className="flex items-center gap-1 text-sm text-muted-foreground">
          © 2026, made with
          <Heart className="h-4 w-4 fill-red-500 text-red-500" />
          by
          <Link
            href="https://www.creative-tim.com"
            className="font-medium text-foreground hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            Creative Tim
          </Link>
          for a better web.
        </p>
        <nav className="flex gap-4 text-sm">
          <Link
            href="https://www.creative-tim.com"
            className="text-muted-foreground hover:text-foreground"
            target="_blank"
            rel="noopener noreferrer"
          >
            Creative Tim
          </Link>
          <Link
            href="https://www.creative-tim.com/presentation"
            className="text-muted-foreground hover:text-foreground"
            target="_blank"
            rel="noopener noreferrer"
          >
            About Us
          </Link>
          <Link
            href="https://www.creative-tim.com/blog"
            className="text-muted-foreground hover:text-foreground"
            target="_blank"
            rel="noopener noreferrer"
          >
            Blog
          </Link>
          <Link
            href="https://www.creative-tim.com/license"
            className="text-muted-foreground hover:text-foreground"
            target="_blank"
            rel="noopener noreferrer"
          >
            License
          </Link>
        </nav>
      </div>
    </footer>
  );
}
