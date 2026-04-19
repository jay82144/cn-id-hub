import React, { useState, useEffect, useCallback } from "react";
import api from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Badge } from "../../components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { RefreshCw, Filter, ChevronLeft, ChevronRight } from "lucide-react";

const ACTION_COLORS = {
  create: "bg-green-500/10 text-green-500",
  update: "bg-blue-500/10 text-blue-500",
  delete: "bg-red-500/10 text-red-500",
  login: "bg-purple-500/10 text-purple-500",
  logout: "bg-gray-500/10 text-gray-500",
  password_change: "bg-yellow-500/10 text-yellow-500",
  role_change: "bg-orange-500/10 text-orange-500",
  app_access: "bg-cyan-500/10 text-cyan-500",
  settings_change: "bg-pink-500/10 text-pink-500",
};

const RESOURCE_ICONS = {
  user: "👤",
  company: "🏢",
  app: "📱",
  role: "🎭",
  employee: "👥",
  settings: "⚙️",
  api_key: "🔑",
  company_app: "🔗",
  migrations: "🗃️",
  user_app: "📲",
  user_role: "🏷️",
};

export default function AuditLogsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [actions, setActions] = useState([]);
  const [resourceTypes, setResourceTypes] = useState([]);
  const limit = 20;

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      let url = `/admin/audit-logs?limit=${limit}&offset=${offset}`;
      if (actionFilter) url += `&action=${actionFilter}`;
      if (resourceFilter) url += `&resource_type=${resourceFilter}`;
      
      const response = await api.get(url);
      setLogs(response.data.logs);
      setTotal(response.data.total);
    } catch (error) {
      console.error("Failed to fetch audit logs:", error);
    } finally {
      setLoading(false);
    }
  }, [offset, actionFilter, resourceFilter]);

  const fetchActions = async () => {
    try {
      const response = await api.get("/admin/audit-logs/actions");
      setActions(response.data.actions);
      setResourceTypes(response.data.resource_types);
    } catch (error) {
      console.error("Failed to fetch actions:", error);
    }
  };

  useEffect(() => {
    fetchActions();
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="space-y-6" data-testid="audit-logs-page">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Audit Logs</h1>
          <p className="text-muted-foreground">Track all admin actions and changes</p>
        </div>
        <Button onClick={fetchLogs} variant="outline" disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-4 p-4 bg-muted/50 rounded-lg" data-testid="audit-filters">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">Filters:</span>
        </div>
        
        <Select 
          value={actionFilter} 
          onValueChange={(val) => { setActionFilter(val === "all" ? "" : val); setOffset(0); }}
        >
          <SelectTrigger className="w-[180px]" data-testid="action-filter">
            <SelectValue placeholder="All Actions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Actions</SelectItem>
            {actions.map((action) => (
              <SelectItem key={action} value={action}>
                {action.replace("_", " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select 
          value={resourceFilter} 
          onValueChange={(val) => { setResourceFilter(val === "all" ? "" : val); setOffset(0); }}
        >
          <SelectTrigger className="w-[180px]" data-testid="resource-filter">
            <SelectValue placeholder="All Resources" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Resources</SelectItem>
            {resourceTypes.map((type) => (
              <SelectItem key={type} value={type}>
                {RESOURCE_ICONS[type] || "📄"} {type.replace("_", " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="ml-auto text-sm text-muted-foreground">
          {total} event{total !== 1 ? "s" : ""} found
        </div>
      </div>

      {/* Table */}
      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[180px]">Timestamp</TableHead>
              <TableHead className="w-[100px]">Action</TableHead>
              <TableHead className="w-[120px]">Resource</TableHead>
              <TableHead>Details</TableHead>
              <TableHead className="w-[200px]">User</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : logs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                  No audit logs found
                </TableCell>
              </TableRow>
            ) : (
              logs.map((log) => (
                <TableRow key={log.id} data-testid={`audit-log-${log.id}`}>
                  <TableCell className="font-mono text-xs">
                    {formatTimestamp(log.timestamp)}
                  </TableCell>
                  <TableCell>
                    <Badge 
                      variant="secondary" 
                      className={ACTION_COLORS[log.action] || "bg-gray-500/10"}
                    >
                      {log.action}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span>{RESOURCE_ICONS[log.resource_type] || "📄"}</span>
                      <span className="text-sm">{log.resource_type}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="text-sm">{log.details || "-"}</span>
                      <span className="text-xs text-muted-foreground font-mono">
                        ID: {log.resource_id?.slice(0, 8)}...
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="text-sm">{log.user_email}</span>
                      <span className="text-xs text-muted-foreground font-mono">
                        {log.user_id?.slice(0, 8)}...
                      </span>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {total > limit && (
        <div className="flex items-center justify-between" data-testid="pagination">
          <div className="text-sm text-muted-foreground">
            Showing {offset + 1} - {Math.min(offset + limit, total)} of {total}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <span className="text-sm text-muted-foreground px-2">
              Page {currentPage} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
