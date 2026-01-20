"use client";

import * as React from "react";
import { X, Info } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type AlertVariant = "default" | "success" | "warning" | "destructive" | "info";

interface DismissableAlertProps {
  variant?: AlertVariant;
  showIcon?: boolean;
  children: React.ReactNode;
  onDismiss?: () => void;
}

const variantStyles: Record<AlertVariant, string> = {
  default: "bg-gray-800 text-white border-gray-800",
  success: "bg-green-500 text-white border-green-500",
  warning: "bg-orange-500 text-white border-orange-500",
  destructive: "bg-red-500 text-white border-red-500",
  info: "bg-gray-800 text-white border-gray-800",
};

export function DismissableAlert({
  variant = "default",
  showIcon = false,
  children,
  onDismiss,
}: DismissableAlertProps) {
  const [isVisible, setIsVisible] = React.useState(true);

  const handleDismiss = () => {
    setIsVisible(false);
    onDismiss?.();
  };

  if (!isVisible) return null;

  return (
    <Alert
      className={cn(
        "flex items-center justify-between",
        variantStyles[variant]
      )}
    >
      <div className="flex items-center gap-3">
        {showIcon && <Info className="h-5 w-5" />}
        <AlertDescription className="text-current">{children}</AlertDescription>
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 hover:bg-white/20"
        onClick={handleDismiss}
      >
        <X className="h-4 w-4" />
      </Button>
    </Alert>
  );
}
