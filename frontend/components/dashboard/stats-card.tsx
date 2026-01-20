import * as React from "react";
import { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatsCardProps {
  title: string;
  value: string;
  change: string;
  changeType: "positive" | "negative";
  icon: LucideIcon;
  iconBgColor?: string;
}

export function StatsCard({
  title,
  value,
  change,
  changeType,
  icon: Icon,
  iconBgColor = "bg-gray-900",
}: StatsCardProps) {
  return (
    <Card className="relative overflow-hidden">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div
            className={cn(
              "flex h-12 w-12 items-center justify-center rounded-lg shadow-lg",
              iconBgColor
            )}
          >
            <Icon className="h-6 w-6 text-white" />
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground">{title}</p>
            <h4 className="text-2xl font-bold">{value}</h4>
          </div>
        </div>
        <div className="mt-4 border-t pt-3">
          <p className="text-sm">
            <span
              className={cn(
                "font-semibold",
                changeType === "positive" ? "text-green-500" : "text-red-500"
              )}
            >
              {change}
            </span>
            <span className="text-muted-foreground"> than last week</span>
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
