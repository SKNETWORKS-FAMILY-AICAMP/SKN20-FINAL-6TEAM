"use client";

import * as React from "react";
import Link from "next/link";
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
import { Badge } from "@/components/ui/badge";

interface Author {
  id: string;
  name: string;
  email: string;
  avatar: string;
  role: string;
  department: string;
  status: "online" | "offline";
  employedDate: string;
}

interface AuthorsTableProps {
  authors: Author[];
}

export function AuthorsTable({ authors }: AuthorsTableProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Authors Table</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="uppercase text-xs">author</TableHead>
              <TableHead className="uppercase text-xs">function</TableHead>
              <TableHead className="uppercase text-xs">status</TableHead>
              <TableHead className="uppercase text-xs">employed</TableHead>
              <TableHead className="uppercase text-xs"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {authors.map((author) => (
              <TableRow key={author.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Avatar>
                      <AvatarImage src={author.avatar} alt={author.name} />
                      <AvatarFallback>{author.name.charAt(0)}</AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="font-medium">{author.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {author.email}
                      </p>
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <p className="font-medium">{author.role}</p>
                  <p className="text-sm text-muted-foreground">
                    {author.department}
                  </p>
                </TableCell>
                <TableCell>
                  <Badge
                    variant={author.status === "online" ? "success" : "secondary"}
                  >
                    {author.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {author.employedDate}
                </TableCell>
                <TableCell>
                  <Link
                    href="#"
                    className="text-sm font-medium text-muted-foreground hover:text-foreground"
                  >
                    Edit
                  </Link>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
