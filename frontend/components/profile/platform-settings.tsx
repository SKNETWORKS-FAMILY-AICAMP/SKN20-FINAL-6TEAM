"use client";

import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

interface SettingItem {
  id: string;
  label: string;
  checked: boolean;
}

interface SettingsGroup {
  title: string;
  items: SettingItem[];
}

interface PlatformSettingsProps {
  groups: SettingsGroup[];
  onSettingChange?: (groupTitle: string, itemId: string, checked: boolean) => void;
}

export function PlatformSettings({
  groups,
  onSettingChange,
}: PlatformSettingsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Platform Settings</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {groups.map((group) => (
          <div key={group.title}>
            <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {group.title}
            </p>
            <div className="space-y-4">
              {group.items.map((item) => (
                <div key={item.id} className="flex items-center justify-between">
                  <Label
                    htmlFor={item.id}
                    className="cursor-pointer text-sm font-normal"
                  >
                    {item.label}
                  </Label>
                  <Switch
                    id={item.id}
                    defaultChecked={item.checked}
                    onCheckedChange={(checked) =>
                      onSettingChange?.(group.title, item.id, checked)
                    }
                  />
                </div>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
