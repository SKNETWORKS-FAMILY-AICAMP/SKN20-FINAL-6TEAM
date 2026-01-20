"use client";

import * as React from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Clock } from "lucide-react";

interface ChartCardProps {
  title: string;
  description: string;
  lastUpdated: string;
  data: Array<{ name: string; value: number }>;
  type: "bar" | "line";
  color?: string;
}

export function ChartCard({
  title,
  description,
  lastUpdated,
  data,
  type,
  color = "#4ade80",
}: ChartCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            {type === "bar" ? (
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 12 }}
                />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} />
              </BarChart>
            ) : (
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 12 }}
                />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={color}
                  strokeWidth={2}
                  dot={{ fill: color, strokeWidth: 2 }}
                />
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      </CardHeader>
      <CardContent>
        <CardTitle className="text-lg">{title}</CardTitle>
        <p className="text-sm text-muted-foreground">{description}</p>
        <div className="mt-4 flex items-center gap-1 text-sm text-muted-foreground">
          <Clock className="h-4 w-4" />
          <span>{lastUpdated}</span>
        </div>
      </CardContent>
    </Card>
  );
}
