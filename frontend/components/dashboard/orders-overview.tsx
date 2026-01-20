"use client";

import * as React from "react";
import {
  Bell,
  CreditCard,
  ShoppingCart,
  Key,
  Package,
  ArrowUp,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Order {
  id: string;
  title: string;
  date: string;
  icon: "bell" | "card" | "cart" | "key" | "package";
  color: string;
}

interface OrdersOverviewProps {
  orders: Order[];
  changePercent: string;
}

const iconMap = {
  bell: Bell,
  card: CreditCard,
  cart: ShoppingCart,
  key: Key,
  package: Package,
};

const colorMap: Record<string, string> = {
  green: "bg-green-500",
  red: "bg-red-500",
  blue: "bg-blue-500",
  orange: "bg-orange-500",
  gray: "bg-gray-500",
};

export function OrdersOverview({ orders, changePercent }: OrdersOverviewProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Orders Overview</CardTitle>
        <p className="flex items-center gap-1 text-sm text-muted-foreground">
          <ArrowUp className="h-4 w-4 text-green-500" />
          <span>
            <strong className="text-green-500">{changePercent}</strong> this
            month
          </span>
        </p>
      </CardHeader>
      <CardContent>
        <div className="relative space-y-6">
          {/* Timeline line */}
          <div className="absolute left-[11px] top-3 h-[calc(100%-24px)] w-0.5 bg-border" />

          {orders.map((order) => {
            const Icon = iconMap[order.icon];
            return (
              <div key={order.id} className="relative flex items-start gap-4">
                <div
                  className={cn(
                    "relative z-10 flex h-6 w-6 items-center justify-center rounded-full",
                    colorMap[order.color] || "bg-gray-500"
                  )}
                >
                  <Icon className="h-3 w-3 text-white" />
                </div>
                <div className="flex-1">
                  <p className="font-medium">{order.title}</p>
                  <p className="text-sm text-muted-foreground">{order.date}</p>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
