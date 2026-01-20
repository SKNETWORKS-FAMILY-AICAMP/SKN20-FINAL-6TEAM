"use client";

import * as React from "react";
import { Pencil } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

interface ProfileInfoProps {
  bio: string;
  details: {
    label: string;
    value: string;
  }[];
  socialLinks?: {
    platform: string;
    url: string;
    icon: React.ReactNode;
  }[];
}

export function ProfileInfo({ bio, details, socialLinks }: ProfileInfoProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Profile Information</CardTitle>
        <Button variant="ghost" size="icon">
          <Pencil className="h-4 w-4" />
        </Button>
      </CardHeader>
      <CardContent>
        <p className="mb-4 text-sm text-muted-foreground">{bio}</p>
        <Separator className="my-4" />
        <ul className="space-y-3">
          {details.map((detail, index) => (
            <li key={index} className="flex items-center gap-2 text-sm">
              <span className="font-medium text-muted-foreground">
                {detail.label}:
              </span>
              <span>{detail.value}</span>
            </li>
          ))}
          {socialLinks && socialLinks.length > 0 && (
            <li className="flex items-center gap-2 text-sm">
              <span className="font-medium text-muted-foreground">social:</span>
              <div className="flex gap-2">
                {socialLinks.map((link, index) => (
                  <a
                    key={index}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-foreground"
                  >
                    {link.icon}
                  </a>
                ))}
              </div>
            </li>
          )}
        </ul>
      </CardContent>
    </Card>
  );
}
