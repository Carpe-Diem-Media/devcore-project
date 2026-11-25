Application.put_env(:ash, :default_string_length_count, :codepoints)
{:ok, _} = Application.ensure_all_started(:ash_postgres)
{:ok, _} = Application.ensure_all_started(:ash_ai)
Postgrex.Types.define(DevCoreRehearsal.Types, [AshPostgres.Extensions.Vector] ++ Ecto.Adapters.Postgres.extensions(), [])

defmodule DevCoreRehearsal.Repo do
  use AshPostgres.Repo, otp_app: :ash_postgres
  def installed_extensions, do: ["ash-functions", "vector"]
  def min_pg_version, do: %Version{major: 18, minor: 0, patch: 0}
end

defmodule DevCoreRehearsal.Model do
  @behaviour AshAi.EmbeddingModel

  def dimensions(_opts), do: 2

  def generate(texts, _opts) do
    {:ok, Enum.map(texts, fn
      "first" -> [1.0, 0.0]
      "second" -> [0.0, 1.0]
    end)}
  end
end

defmodule DevCoreRehearsal.Embedding do
  use Ash.Resource,
    domain: DevCoreRehearsal.Domain,
    data_layer: AshPostgres.DataLayer,
    extensions: [AshAi]

  vectorize do
    strategy :manual
    attributes title: :embedding
    embedding_model DevCoreRehearsal.Model
  end

  postgres do
    table "devcore_embeddings"
    repo DevCoreRehearsal.Repo
  end
  actions do
    defaults [:read, create: [:title]]
  end
  attributes do
    uuid_primary_key :id
    attribute :title, :string, allow_nil?: false, public?: true
  end
  calculations do
    calculate :distance, :float, expr(vector_cosine_distance(embedding, ^arg(:target))) do
      argument :target, :vector, allow_nil?: false
    end
  end
end

defmodule DevCoreRehearsal.Domain do
  use Ash.Domain, validate_config_inclusion?: false
  resources do
    resource DevCoreRehearsal.Embedding
  end
end

Application.put_env(:ash_postgres, DevCoreRehearsal.Repo,
  hostname: System.fetch_env!("TEST_DATABASE_HOST"),
  port: String.to_integer(System.fetch_env!("TEST_DATABASE_PORT")),
  database: System.fetch_env!("TEST_DATABASE_NAME"),
  username: System.fetch_env!("TEST_DATABASE_USERNAME"),
  password: System.fetch_env!("TEST_DATABASE_PASSWORD"),
  types: DevCoreRehearsal.Types
)

{:ok, _} = DevCoreRehearsal.Repo.start_link()
root = System.fetch_env!("DEVCORE_ASH_FIXTURE_DIR")
migrations = Path.join(root, "migrations")
Application.put_env(:voelgoed_ai, :ecto_repos, [DevCoreRehearsal.Repo])
AshPostgres.MigrationGenerator.generate([DevCoreRehearsal.Domain],
  migration_path: migrations, snapshot_path: Path.join(root, "snapshots"),
  name: "vector_rehearsal", format: false
)
Ecto.Migrator.run(DevCoreRehearsal.Repo, migrations, :up, all: true)

alias DevCoreRehearsal.Embedding
for title <- ["first", "second"] do
  Embedding
  |> Ash.create!(%{title: title})
  |> Ash.update!(%{}, action: :ash_ai_update_embeddings)
end

{:ok, [target]} = DevCoreRehearsal.Model.generate(["first"], [])
require Ash.Query

[%{title: "first", distance: +0.0, embedding: %Ash.Vector{}},
 %{title: "second", distance: 1.0, embedding: %Ash.Vector{}}] =
  Embedding
  |> Ash.Query.select([:title, :embedding])
  |> Ash.Query.load(distance: %{target: target})
  |> Ash.Query.sort(distance: {%{target: target}, :asc})
  |> Ash.read!()

IO.puts("Ash-generated migration and Postgrex vector/cosine round trip passed")
