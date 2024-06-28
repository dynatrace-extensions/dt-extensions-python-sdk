from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

PREFIX_HOST = "HOST"
PREFIX_PG = "PROCESS_GROUP"
PREFIX_PGI = "PROCESS_GROUP_INSTANCE"


@dataclass
class EntryProperties:
    technologies: list[str]
    pg_technologies: list[str]

    @staticmethod
    def from_json(json_data: dict) -> EntryProperties:
        technologies = json_data.get("Technologies", "").split(",")
        pg_technologies = json_data.get("pgTechnologies", "").split(",")
        return EntryProperties(technologies, pg_technologies)


@dataclass
class PortBinding:
    ip: str
    port: int

    @staticmethod
    def from_string(data: str) -> PortBinding:
        ip, port = data.split("_")
        return PortBinding(ip, int(port))


@dataclass
class ProcessProperties:
    cmd_line: str | None
    exe_path: str | None
    parent_pid: int | None
    work_dir: str | None
    listening_ports: list[int]
    port_bindings: list[PortBinding]
    docker_mount: str | None
    docker_container_id: str | None
    listening_internal_ports: str | None

    @staticmethod
    def from_json(json_data: dict) -> ProcessProperties:
        cmd_line = json_data.get("CmdLine")
        exe_path = json_data.get("ExePath")
        parent_pid = int(json_data.get("ParentPid", -1))
        work_dir = json_data.get("WorkDir")
        listening_ports = [int(p) for p in json_data.get("ListeningPorts", "").split(" ") if p != ""]
        port_bindings = [PortBinding.from_string(p) for p in json_data.get("PortBindings", "").split(";") if p != ""]
        docker_mount = json_data.get("DockerMount")
        docker_container_id = json_data.get("DockerContainerId")
        listening_internal_ports = json_data.get("ListeningInternalPorts")
        return ProcessProperties(
            cmd_line,
            exe_path,
            parent_pid,
            work_dir,
            listening_ports,
            port_bindings,
            docker_mount,
            docker_container_id,
            listening_internal_ports,
        )


@dataclass
class Process:
    pid: int
    process_name: str
    properties: ProcessProperties

    @staticmethod
    def from_json(json_data: dict) -> Process:
        pid = int(json_data.get("pid", "-1"))
        process_name = json_data.get("process_name", "unknown-process-name")
        all_properties = {}
        for p in json_data.get("properties", []):
            all_properties.update(p)
        properties = ProcessProperties.from_json(all_properties)
        return Process(pid, process_name, properties)


@dataclass
class Entry:
    group_id: str
    node_id: str
    group_instance_id: str
    process_type: int
    group_name: str
    processes: list[Process]
    properties: EntryProperties

    @staticmethod
    def from_json(json_data: dict) -> Entry:
        group_id = json_data.get("group_id", "0X0000000000000000")
        group_id = f"{PREFIX_PG}-{group_id[-16:]}"

        node_id = json_data.get("node_id", "0X0000000000000000")

        group_instance_id = json_data.get("group_instance_id", "0X0000000000000000")
        group_instance_id = f"{PREFIX_PGI}-{group_instance_id[-16:]}"

        process_type = int(json_data.get("process_type", "0"))
        group_name = json_data.get("group_name", "unknown-group-name")
        processes = [Process.from_json(p) for p in json_data.get("processes", [])]

        # The structure here was never thought out, so we have to check for both keys and merge them into one object
        properties_list = json_data.get("properties", [])
        technologies = [p for p in properties_list if "Technologies" in p]
        if technologies:
            technologies = technologies[0]["Technologies"].split(",")

        pg_technologies = [p for p in properties_list if "pgTechnologies" in p]
        if pg_technologies:
            pg_technologies = pg_technologies[0]["pgTechnologies"].split(",")
        properties = EntryProperties(technologies or [], pg_technologies or [])

        return Entry(group_id, node_id, group_instance_id, process_type, group_name, processes, properties)


@dataclass
class Snapshot:
    host_id: str
    entries: list[Entry]

    @staticmethod
    def parse_from_file(snapshot_file: Path | str | None = None) -> Snapshot:
        """Returns a process snapshot object like EF1.0 used to do"""

        if snapshot_file is None:
            snapshot_file = find_log_dir() / "plugin" / "oneagent_latest_snapshot.log"

        with open(snapshot_file) as f:
            snapshot_json = json.load(f)

        host_id = snapshot_json.get("host_id", "0X0000000000000000")
        host_id = f"{PREFIX_HOST}-{host_id[-16:]}"
        entries = [Entry.from_json(e) for e in snapshot_json.get("entries", [])]
        return Snapshot(host_id, entries)

    # Returns list of Process groups matching a technology. Use to simulate activation
    def get_process_groups_by_technology(self, technology: str) -> list[Entry]:
        pgs = []
        for entry in self.entries:
            if technology in entry.properties.technologies:
                pgs.append(entry)

        return pgs


def find_config_directory() -> Path:
    """
    Attempt to find the OneAgent config directory.
    Note, the user can never modify these directories
    Windows -> https://docs.dynatrace.com/docs/shortlink/oneagent-disk-requirements-windows#oneagent-files-aging-mechanism
    Linux -> https://docs.dynatrace.com/docs/shortlink/oneagent-disk-requirements-linux#sizes
    """
    config_dir_base = os.path.expandvars("%PROGRAMDATA%") if os.name == "nt" else "/var/lib"
    config_dir = Path(config_dir_base) / "dynatrace" / "oneagent" / "agent" / "config"
    if config_dir.exists():
        return config_dir
    file_path = Path(__file__).resolve()

    while file_path.parent != file_path:
        file_path = file_path.parent
        if file_path.name == "agent":
            return file_path / "config"

    msg = "Could not find the OneAgent config directory"
    raise Exception(msg)


def find_log_dir() -> Path:
    """
    Attempt to find the OneAgent log directory.
    This is always stored in the installation.conf file.
    So we attempt to find the installation.conf file and read the LogDir property
    Returns: the Path to the log directory
    """
    config_dir = find_config_directory()
    installation_conf = config_dir / "installation.conf"
    if not installation_conf.exists():
        msg = f"Could not find installation.conf at {installation_conf}"
        raise Exception(msg)

    with open(installation_conf) as f:
        for line in f:
            if line.startswith("LogDir"):
                log_dir = line.split("=")[1].strip()
                return Path(log_dir)
    msg = f"Could not find LogDir in {installation_conf}"
    raise Exception(msg)
