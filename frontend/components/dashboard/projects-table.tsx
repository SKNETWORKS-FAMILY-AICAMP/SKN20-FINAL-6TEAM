"use client";

import * as React from "react";
import Image from "next/image";
import { MoreVertical, CheckCircle } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

interface Member {
  name: string;
  avatar: string;
}

interface Project {
  id: string;
  name: string;
  logo: string;
  members: Member[];
  budget: string;
  completion: number;
}

interface ProjectsTableProps {
  projects: Project[];
}

export function ProjectsTable({ projects }: ProjectsTableProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Projects</CardTitle>
          <p className="mt-1 flex items-center gap-1 text-sm text-muted-foreground">
            <CheckCircle className="h-4 w-4 text-blue-500" />
            <span>
              <strong>30 done</strong> this month
            </span>
          </p>
        </div>
        <Button variant="ghost" size="icon">
          <MoreVertical className="h-5 w-5" />
        </Button>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="uppercase text-xs">companies</TableHead>
              <TableHead className="uppercase text-xs">members</TableHead>
              <TableHead className="uppercase text-xs">budget</TableHead>
              <TableHead className="uppercase text-xs">completion</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {projects.map((project) => (
              <TableRow key={project.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted">
                      <Image
                        src={project.logo}
                        alt={project.name}
                        width={24}
                        height={24}
                        className="h-6 w-6"
                      />
                    </div>
                    <span className="font-medium">{project.name}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex -space-x-2">
                    {project.members.map((member, index) => (
                      <Avatar
                        key={index}
                        className="h-8 w-8 border-2 border-background"
                      >
                        <AvatarImage src={member.avatar} alt={member.name} />
                        <AvatarFallback>
                          {member.name.charAt(0)}
                        </AvatarFallback>
                      </Avatar>
                    ))}
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {project.budget}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{project.completion}%</span>
                    <Progress value={project.completion} className="w-20" />
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
