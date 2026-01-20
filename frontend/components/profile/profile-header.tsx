"use client";

import * as React from "react";
import Image from "next/image";
import { Home, MessageSquare, Settings } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface ProfileHeaderProps {
  name: string;
  role: string;
  avatar: string;
  coverImage?: string;
}

export function ProfileHeader({
  name,
  role,
  avatar,
  coverImage = "/images/cover.jpg",
}: ProfileHeaderProps) {
  return (
    <div className="relative mb-6 overflow-hidden rounded-xl">
      {/* Cover Image */}
      <div className="h-48 w-full bg-gradient-to-r from-gray-900 to-gray-800">
        {coverImage && (
          <Image
            src={coverImage}
            alt="Cover"
            fill
            className="object-cover opacity-50"
          />
        )}
      </div>

      {/* Profile Info */}
      <div className="absolute bottom-0 left-0 right-0 flex items-end justify-between p-6">
        <div className="flex items-center gap-4">
          <div className="relative h-20 w-20 overflow-hidden rounded-xl border-4 border-white shadow-lg">
            <Image
              src={avatar}
              alt={name}
              fill
              className="object-cover"
            />
          </div>
          <div className="text-white">
            <h2 className="text-xl font-bold">{name}</h2>
            <p className="text-sm text-gray-300">{role}</p>
          </div>
        </div>

        <Tabs defaultValue="app" className="w-auto">
          <TabsList className="bg-white/20 backdrop-blur">
            <TabsTrigger
              value="app"
              className="gap-2 text-white data-[state=active]:bg-white data-[state=active]:text-gray-900"
            >
              <Home className="h-4 w-4" />
              App
            </TabsTrigger>
            <TabsTrigger
              value="message"
              className="gap-2 text-white data-[state=active]:bg-white data-[state=active]:text-gray-900"
            >
              <MessageSquare className="h-4 w-4" />
              Message
            </TabsTrigger>
            <TabsTrigger
              value="settings"
              className="gap-2 text-white data-[state=active]:bg-white data-[state=active]:text-gray-900"
            >
              <Settings className="h-4 w-4" />
              Settings
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </div>
  );
}
