"use client";

import * as React from "react";
import Image from "next/image";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";

interface Member {
  name: string;
  avatar: string;
}

interface ProjectCardProps {
  projectNumber: number;
  title: string;
  description: string;
  image: string;
  members: Member[];
  href?: string;
}

export function ProjectCard({
  projectNumber,
  title,
  description,
  image,
  members,
  href = "#",
}: ProjectCardProps) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="p-0">
        <div className="relative aspect-video">
          <Image
            src={image}
            alt={title}
            fill
            className="object-cover"
          />
        </div>
      </CardHeader>
      <CardContent className="p-4">
        <p className="text-xs text-muted-foreground">Project #{projectNumber}</p>
        <h3 className="mt-1 text-lg font-semibold">{title}</h3>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
      </CardContent>
      <CardFooter className="flex items-center justify-between p-4 pt-0">
        <Button asChild variant="outline" size="sm">
          <Link href={href}>view project</Link>
        </Button>
        <div className="flex -space-x-2">
          {members.map((member, index) => (
            <Avatar
              key={index}
              className="h-8 w-8 border-2 border-background"
            >
              <AvatarImage src={member.avatar} alt={member.name} />
              <AvatarFallback>{member.name.charAt(0)}</AvatarFallback>
            </Avatar>
          ))}
        </div>
      </CardFooter>
    </Card>
  );
}
