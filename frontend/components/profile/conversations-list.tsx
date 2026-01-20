"use client";

import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";

interface Conversation {
  id: string;
  name: string;
  avatar: string;
  lastMessage: string;
}

interface ConversationsListProps {
  conversations: Conversation[];
  onReply?: (id: string) => void;
}

export function ConversationsList({
  conversations,
  onReply,
}: ConversationsListProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Platform Settings</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {conversations.map((conversation) => (
            <div
              key={conversation.id}
              className="flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <Avatar>
                  <AvatarImage src={conversation.avatar} alt={conversation.name} />
                  <AvatarFallback>
                    {conversation.name.charAt(0)}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-medium">{conversation.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {conversation.lastMessage}
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onReply?.(conversation.id)}
              >
                reply
              </Button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
