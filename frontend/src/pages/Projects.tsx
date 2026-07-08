import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, type Page } from "../lib/api";
import { money } from "../lib/format";
import {
  Badge,
  Card,
  EmptyState,
  Field,
  FilterBar,
  Input,
  PageHeader,
  Pagination,
  Select,
  Spinner,
  Table,
  statusTone,
} from "../components/ui";

interface Project {
  id: number;
  project_code: string;
  project_name: string;
  project_type: string;
  client_name: string;
  city: string;
  status: string;
  budget: string;
}

const STATUSES = ["Active", "Delayed", "On Hold", "Completed"];

export default function Projects() {
  const navigate = useNavigate();
  const [data, setData] = useState<Page<Project>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [city, setCity] = useState("");

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (status) params.set("status", status);
    if (city) params.set("city", city);
    setError(undefined);
    api
      .get<Page<Project>>(`/projects?${params}`)
      .then(setData)
      .catch((e: ApiError) => setError(e.message));
  }, [page, status, city]);

  return (
    <div>
      <PageHeader title="Projects" subtitle="Portfolio of construction projects" />

      <FilterBar>
        <Field label="Status">
          <Select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="City">
          <Input
            placeholder="Filter by city"
            value={city}
            onChange={(e) => {
              setCity(e.target.value);
              setPage(1);
            }}
          />
        </Field>
      </FilterBar>

      {error && <div className="text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={["Code", "Project", "Type", "City", "Status", "Budget"]}>
            {data.items.map((p) => (
              <tr
                key={p.id}
                onClick={() => navigate(`/projects/${p.id}`)}
                className="cursor-pointer hover:bg-slate-50"
              >
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{p.project_code}</td>
                <td className="px-4 py-3 font-medium text-slate-800">{p.project_name}</td>
                <td className="px-4 py-3 text-slate-600">{p.project_type}</td>
                <td className="px-4 py-3 text-slate-600">{p.city}</td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(p.status)}>{p.status}</Badge>
                </td>
                <td className="px-4 py-3 text-slate-600">{money(p.budget)}</td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && <EmptyState message="No projects match these filters." />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}
    </div>
  );
}
