export interface paths {
    "/api/v1/assets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Asset Catalog */
        get: operations["read_asset_catalog_api_v1_assets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/assets/{asset_key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Asset Detail */
        get: operations["read_asset_detail_api_v1_assets__asset_key__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Session */
        get: operations["read_session_api_v1_auth_session_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/evidence": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Evidence List */
        get: operations["read_evidence_list_api_v1_evidence_get"];
        put?: never;
        /** Create Evidence */
        post: operations["create_evidence_api_v1_evidence_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/evidence/{evidence_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Evidence */
        get: operations["read_evidence_api_v1_evidence__evidence_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incident-assignees": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Incident Assignees */
        get: operations["read_incident_assignees_api_v1_incident_assignees_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Incident List */
        get: operations["read_incident_list_api_v1_incidents_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Incident Detail */
        get: operations["read_incident_detail_api_v1_incidents__incident_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}/assignment": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Incident Assignment */
        patch: operations["patch_incident_assignment_api_v1_incidents__incident_id__assignment_patch"];
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Incident Audit */
        get: operations["read_incident_audit_api_v1_incidents__incident_id__audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}/disposition": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Incident Disposition */
        patch: operations["patch_incident_disposition_api_v1_incidents__incident_id__disposition_patch"];
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}/notes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Incident Note */
        post: operations["create_incident_note_api_v1_incidents__incident_id__notes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}/report": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Incident Report */
        get: operations["read_incident_report_api_v1_incidents__incident_id__report_get"];
        /** Put Incident Report */
        put: operations["put_incident_report_api_v1_incidents__incident_id__report_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Incident Status */
        patch: operations["patch_incident_status_api_v1_incidents__incident_id__status_patch"];
        trace?: never;
    };
    "/api/v1/lab/baseline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post Lab Baseline */
        post: operations["post_lab_baseline_api_v1_lab_baseline_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lab/catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Lab Catalog */
        get: operations["get_lab_catalog_api_v1_lab_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lab/context": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Lab Context */
        get: operations["get_lab_context_api_v1_lab_context_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lab/reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post Lab Reset */
        post: operations["post_lab_reset_api_v1_lab_reset_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lab/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Lab Runs */
        get: operations["get_lab_runs_api_v1_lab_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lab/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Lab Run */
        get: operations["get_lab_run_api_v1_lab_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lab/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post Lab Start */
        post: operations["post_lab_start_api_v1_lab_start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/meta": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Metadata */
        get: operations["metadata_api_v1_meta_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/overview/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Overview Summary */
        get: operations["read_overview_summary_api_v1_overview_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/replay": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Replay Bundle */
        get: operations["read_replay_bundle_api_v1_replay_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Users */
        get: operations["read_users_api_v1_users_get"];
        put?: never;
        /** Create User */
        post: operations["create_user_api_v1_users_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch User */
        patch: operations["patch_user_api_v1_users__user_id__patch"];
        trace?: never;
    };
    "/api/v1/users/{user_id}/password-reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reset User Password */
        post: operations["reset_user_password_api_v1_users__user_id__password_reset_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Liveness */
        get: operations["liveness_health_live_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Readiness */
        get: operations["readiness_health_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActiveProfileMetadata */
        ActiveProfileMetadata: {
            /** Profile Id */
            profile_id: string;
            /** Sha256 */
            sha256: string;
            /** Version */
            version: string;
        };
        /** ActiveSchemaMetadata */
        ActiveSchemaMetadata: {
            /** Schema Id */
            schema_id: string;
            /** Version */
            version: string;
        };
        /** AssetCatalogResponse */
        AssetCatalogResponse: {
            /** Assets */
            assets: components["schemas"]["ProductAsset"][];
            /** Disclaimer */
            disclaimer: string;
            /**
             * Domain
             * @constant
             */
            domain: "oil_gas_transfer";
            /**
             * Educational Only
             * @constant
             */
            educational_only: true;
            /**
             * Profile Id
             * @constant
             */
            profile_id: "otsoc.asset_inventory.oil_gas_transfer";
            /** Profile Sha256 */
            profile_sha256: string;
            /**
             * Profile Version
             * @constant
             */
            profile_version: "1.0.0";
            /** Relationships */
            relationships: components["schemas"]["RelationshipDefinition"][];
            /** Zones */
            zones: components["schemas"]["ZoneDefinition"][];
        };
        /** AssetContextDerivationProvenance */
        AssetContextDerivationProvenance: {
            /**
             * Canonicalization Version
             * @constant
             */
            canonicalization_version: "otsoc-canonical-json-1";
            /**
             * Derivation Kind
             * @constant
             */
            derivation_kind: "ASSET_CONTEXT_RESOLUTION";
            /**
             * Educational Only
             * @constant
             */
            educational_only: true;
            /**
             * Ground Truth Used
             * @constant
             */
            ground_truth_used: false;
            /**
             * Inventory Profile
             * @constant
             */
            inventory_profile: "otsoc.asset_inventory.oil_gas_transfer";
            /** Inventory Sha256 */
            inventory_sha256: string;
            /** Inventory Version */
            inventory_version: string;
            /**
             * Resolver Name
             * @constant
             */
            resolver_name: "otsoc_exact_asset_resolver";
            /** Resolver Version */
            resolver_version: string;
            /**
             * Semantic Event Id
             * Format: uuid
             */
            semantic_event_id: string;
            /** Semantic Evidence Integrity Sha256 */
            semantic_evidence_integrity_sha256: string;
        };
        /** AssetContextEvent */
        AssetContextEvent: {
            /**
             * Asset Context Event Id
             * Format: uuid
             */
            asset_context_event_id: string;
            /**
             * Asset Context Schema
             * @constant
             */
            asset_context_schema: "otsoc.asset.context_event";
            /**
             * Asset Context Schema Version
             * @constant
             */
            asset_context_schema_version: "1.0.0";
            /**
             * Canonicalization Version
             * @constant
             */
            canonicalization_version: "otsoc-canonical-json-1";
            /**
             * Derivation Kind
             * @constant
             */
            derivation_kind: "ASSET_CONTEXT_RESOLUTION";
            /**
             * Derived From
             * Format: uuid
             */
            derived_from: string;
            /** Destination Identity Claims */
            destination_identity_claims: components["schemas"]["IdentityClaim"][];
            destination_resolution: components["schemas"]["AssetResolution"];
            /**
             * Ground Truth Used
             * @constant
             */
            ground_truth_used: false;
            /**
             * Inventory Profile
             * @constant
             */
            inventory_profile: "otsoc.asset_inventory.oil_gas_transfer";
            /** Inventory Sha256 */
            inventory_sha256: string;
            /** Inventory Version */
            inventory_version: string;
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /** Relevant Relationships */
            relevant_relationships: components["schemas"]["ResolvedRelationship"][];
            /**
             * Resolver Name
             * @constant
             */
            resolver_name: "otsoc_exact_asset_resolver";
            /** Resolver Version */
            resolver_version: string;
            /**
             * Semantic Event Id
             * Format: uuid
             */
            semantic_event_id: string;
            /** Semantic Evidence Integrity Sha256 */
            semantic_evidence_integrity_sha256: string;
            /**
             * Source Evidence Id
             * Format: uuid
             */
            source_evidence_id: string;
            /** Source Evidence Integrity Sha256 */
            source_evidence_integrity_sha256: string;
            /** Source Identity Claims */
            source_identity_claims: components["schemas"]["IdentityClaim"][];
            source_resolution: components["schemas"]["AssetResolution"];
            target_process_asset: components["schemas"]["AssetResolution"] | null;
        };
        /** AssetDefinition */
        AssetDefinition: {
            /** Asset Key */
            asset_key: string;
            asset_kind: components["schemas"]["AssetKind"];
            asset_role: components["schemas"]["AssetRole"];
            asset_type: components["schemas"]["AssetType"];
            criticality: components["schemas"]["Criticality"];
            /** Display Name */
            display_name: string;
            /** Enabled */
            enabled: boolean;
            /** Identifiers */
            identifiers: components["schemas"]["Identifier"][];
            /** Process Role */
            process_role: string | null;
            /** Protocol Capabilities */
            protocol_capabilities: string[];
            zone_id: components["schemas"]["ZoneId"];
        };
        /** AssetDetailResponse */
        AssetDetailResponse: {
            asset: components["schemas"]["ProductAsset"];
            /** Inbound Relationships */
            inbound_relationships: components["schemas"]["RelationshipDefinition"][];
            /** Outbound Relationships */
            outbound_relationships: components["schemas"]["RelationshipDefinition"][];
            /**
             * Profile Id
             * @constant
             */
            profile_id: "otsoc.asset_inventory.oil_gas_transfer";
            /** Profile Sha256 */
            profile_sha256: string;
            /**
             * Profile Version
             * @constant
             */
            profile_version: "1.0.0";
            zone: components["schemas"]["ZoneDefinition"];
        };
        /**
         * AssetKind
         * @enum {string}
         */
        AssetKind: "CYBER" | "PROCESS";
        /** AssetOverviewSummary */
        AssetOverviewSummary: {
            /**
             * Cyber
             * @constant
             */
            cyber: 6;
            /** Enabled */
            enabled: number;
            /**
             * Process
             * @constant
             */
            process: 5;
            /**
             * Total
             * @constant
             */
            total: 11;
        };
        /** AssetResolution */
        AssetResolution: {
            /** Asset Id */
            asset_id: string | null;
            /** Asset Key */
            asset_key: string | null;
            asset_kind: components["schemas"]["AssetKind"] | null;
            asset_role: components["schemas"]["AssetRole"] | null;
            asset_type: components["schemas"]["AssetType"] | null;
            criticality: components["schemas"]["Criticality"] | null;
            /** Enabled */
            enabled: boolean | null;
            /** Known Asset */
            known_asset: boolean;
            status: components["schemas"]["ResolutionStatus"];
            zone_id: components["schemas"]["ZoneId"] | null;
        };
        /**
         * AssetRole
         * @enum {string}
         */
        AssetRole: "CONTROL_EXECUTION" | "OPERATOR_INTERFACE" | "ENGINEERING_MAINTENANCE" | "ENTERPRISE_USER" | "PASSIVE_MONITOR" | "ANALYST_PLATFORM" | "SOURCE_STORAGE" | "LIQUID_TRANSFER" | "TRANSFER_PATH" | "FLOW_CONTROL" | "DESTINATION_STORAGE";
        /**
         * AssetType
         * @enum {string}
         */
        AssetType: "OT_CONTROLLER" | "HUMAN_MACHINE_INTERFACE" | "ENGINEERING_WORKSTATION" | "IT_WORKSTATION" | "MONITORING_SENSOR" | "OT_SOC_PLATFORM" | "SOURCE_TANK" | "TRANSFER_PUMP" | "PIPELINE" | "CONTROL_VALVE" | "RECEIVING_TANK";
        /** AssignableUserListResponse */
        AssignableUserListResponse: {
            /** Items */
            items: components["schemas"]["AssignableUserResponse"][];
        };
        /** AssignableUserResponse */
        AssignableUserResponse: {
            /** Display Name */
            display_name: string;
            /**
             * Role
             * @enum {string}
             */
            role: "ADMIN" | "SOC_ANALYST";
            /**
             * User Id
             * Format: uuid
             */
            user_id: string;
            /** Username */
            username: string;
        };
        /** AuthorizationDimensions */
        AuthorizationDimensions: {
            communication_path_approved: components["schemas"]["DimensionStatus"];
            destination_asset_known: components["schemas"]["DimensionStatus"];
            destination_zone_expected: components["schemas"]["DimensionStatus"];
            operation_approved: components["schemas"]["DimensionStatus"];
            point_classification_allows: components["schemas"]["DimensionStatus"];
            protocol_approved: components["schemas"]["DimensionStatus"];
            source_asset_known: components["schemas"]["DimensionStatus"];
            source_role_approved: components["schemas"]["DimensionStatus"];
            source_zone_expected: components["schemas"]["DimensionStatus"];
        };
        /** CanonicalAddress */
        CanonicalAddress: {
            /** Address Offset */
            address_offset: number | null;
            /** Display Reference */
            display_reference: number | null;
            /** Table Type */
            table_type: string | null;
            /** Unit Id */
            unit_id: number;
        };
        /**
         * CaptureMode
         * @enum {string}
         */
        CaptureMode: "OFFLINE_FIXTURE" | "IN_MEMORY_TEST";
        /** CommunicationPolicyFinding */
        CommunicationPolicyFinding: {
            /** Analyst Readable Statement */
            analyst_readable_statement: string;
            /**
             * Asset Context Event Id
             * Format: uuid
             */
            asset_context_event_id: string;
            /**
             * Canonicalization Version
             * @constant
             */
            canonicalization_version: "otsoc-canonical-json-1";
            /**
             * Derivation Kind
             * @constant
             */
            derivation_kind: "COMMUNICATION_POLICY_EVALUATION";
            /** Derived From */
            derived_from: [
                string,
                string
            ];
            /** Destination Asset Id */
            destination_asset_id: string | null;
            /** Destination Asset Key */
            destination_asset_key: string | null;
            destination_resolution: components["schemas"]["ResolutionStatus"];
            destination_role: components["schemas"]["AssetRole"] | null;
            destination_zone: components["schemas"]["ZoneId"] | null;
            dimension_results: components["schemas"]["AuthorizationDimensions"];
            /**
             * Evaluated At
             * Format: date-time
             */
            evaluated_at: string;
            /**
             * Evaluator Name
             * @constant
             */
            evaluator_name: "otsoc_communication_policy_evaluator";
            /** Evaluator Version */
            evaluator_version: string;
            /** Fictional Target Component */
            fictional_target_component: string | null;
            /**
             * Finding Id
             * Format: uuid
             */
            finding_id: string;
            /**
             * Finding Schema
             * @constant
             */
            finding_schema: "otsoc.communication_policy.finding";
            /**
             * Finding Schema Version
             * @constant
             */
            finding_schema_version: "1.0.0";
            /** Function Code */
            function_code: number;
            function_semantic: components["schemas"]["FunctionSemantic"] | null;
            /**
             * Ground Truth Used
             * @constant
             */
            ground_truth_used: false;
            /**
             * Inventory Profile
             * @constant
             */
            inventory_profile: "otsoc.asset_inventory.oil_gas_transfer";
            /** Inventory Sha256 */
            inventory_sha256: string;
            /** Inventory Version */
            inventory_version: string;
            /**
             * Malicious Intent Inferred
             * @constant
             */
            malicious_intent_inferred: false;
            /** Matched Path Id */
            matched_path_id: string | null;
            /** Matched Rule Id */
            matched_rule_id: string | null;
            operation_category: components["schemas"]["OperationCategory"];
            operation_compatibility: components["schemas"]["OperationCompatibility"];
            point_access_class: components["schemas"]["PointAccessClass"] | null;
            /**
             * Policy Profile
             * @constant
             */
            policy_profile: "otsoc.communication_policy.oil_gas_transfer";
            /** Policy Sha256 */
            policy_sha256: string;
            policy_status: components["schemas"]["PolicyStatus"];
            /** Policy Version */
            policy_version: string;
            /** Protocol */
            protocol: string;
            /**
             * Protocol Profile
             * @constant
             */
            protocol_profile: "otsoc.synthetic_modbus.oil_gas_transfer";
            /** Protocol Profile Sha256 */
            protocol_profile_sha256: string;
            /**
             * Protocol Profile Version
             * @constant
             */
            protocol_profile_version: "1.0.0";
            reason_code: components["schemas"]["PolicyReasonCode"];
            /**
             * Semantic Event Id
             * Format: uuid
             */
            semantic_event_id: string;
            /** Semantic Evidence Integrity Sha256 */
            semantic_evidence_integrity_sha256: string;
            /** Source Asset Id */
            source_asset_id: string | null;
            /** Source Asset Key */
            source_asset_key: string | null;
            /**
             * Source Evidence Id
             * Format: uuid
             */
            source_evidence_id: string;
            /** Source Evidence Integrity Sha256 */
            source_evidence_integrity_sha256: string;
            source_resolution: components["schemas"]["ResolutionStatus"];
            source_role: components["schemas"]["AssetRole"] | null;
            source_zone: components["schemas"]["ZoneId"] | null;
            /** Statement Template Id */
            statement_template_id: string;
            /** Target Point */
            target_point: string | null;
        };
        /** CorrelationDerivationProvenance */
        CorrelationDerivationProvenance: {
            /**
             * Canonicalization Version
             * @constant
             */
            canonicalization_version: "otsoc-canonical-json-1";
            /** Configuration Hash */
            configuration_hash: string | null;
            /**
             * Correlation Profile Id
             * @constant
             */
            correlation_profile_id: "otsoc.correlation.oil_gas_transfer";
            /** Correlation Profile Sha256 */
            correlation_profile_sha256: string;
            /** Correlation Profile Version */
            correlation_profile_version: string;
            /** Correlation Rule Id */
            correlation_rule_id: string;
            /** Correlation Rule Version */
            correlation_rule_version: string;
            /**
             * Derivation Kind
             * @constant
             */
            derivation_kind: "CYBER_PHYSICAL_CORRELATION";
            /**
             * Domain
             * @constant
             */
            domain: "oil_gas_transfer";
            /**
             * Educational Only
             * @constant
             */
            educational_only: true;
            /**
             * Evaluator Name
             * @constant
             */
            evaluator_name: "otsoc_offline_correlation_evaluator";
            /** Evaluator Version */
            evaluator_version: string;
            /**
             * Ground Truth Used
             * @constant
             */
            ground_truth_used: false;
            /**
             * Inventory Profile Id
             * @constant
             */
            inventory_profile_id: "otsoc.asset_inventory.oil_gas_transfer";
            /** Inventory Profile Sha256 */
            inventory_profile_sha256: string;
            /**
             * Inventory Profile Version
             * @constant
             */
            inventory_profile_version: "1.0.0";
            /** Parent References */
            parent_references: components["schemas"]["EvidenceParentReference"][];
            /** Parent Set Sha256 */
            parent_set_sha256: string;
            /**
             * Policy Profile Id
             * @constant
             */
            policy_profile_id: "otsoc.communication_policy.oil_gas_transfer";
            /** Policy Profile Sha256 */
            policy_profile_sha256: string;
            /**
             * Policy Profile Version
             * @constant
             */
            policy_profile_version: "1.0.0";
            /**
             * Process Model Version
             * @constant
             */
            process_model_version: "3.6";
            /**
             * Protocol Profile Id
             * @constant
             */
            protocol_profile_id: "otsoc.synthetic_modbus.oil_gas_transfer";
            /** Protocol Profile Sha256 */
            protocol_profile_sha256: string;
            /**
             * Protocol Profile Version
             * @constant
             */
            protocol_profile_version: "1.0.0";
            /** Simulation Id */
            simulation_id: string | null;
            /**
             * Simulator Version
             * @constant
             */
            simulator_version: "3.0.0";
            /**
             * Telemetry Schema
             * @constant
             */
            telemetry_schema: "otsoc.simulator.telemetry";
            /**
             * Telemetry Schema Version
             * @constant
             */
            telemetry_schema_version: "2.0.0";
        };
        /** CorrelationOverviewSummary */
        CorrelationOverviewSummary: {
            /** Correlated */
            correlated: number;
            /** Indeterminate */
            indeterminate: number;
            /** Insufficient Evidence */
            insufficient_evidence: number;
            /** Not Correlated */
            not_correlated: number;
            /** Total */
            total: number;
        };
        /**
         * CorrelationReasonCode
         * @enum {string}
         */
        CorrelationReasonCode: "PARENT_EVIDENCE_NOT_VERIFIED" | "PROFILE_VERSION_UNSUPPORTED" | "PROFILE_DIGEST_MISMATCH" | "UNSUPPORTED_CORRELATION_RULE" | "RUN_ID_MISMATCH" | "CONFIGURATION_MISMATCH" | "SIMULATOR_VERSION_MISMATCH" | "CLOCK_SEQUENCE_MISMATCH" | "ASSET_RELATION_MISMATCH" | "POINT_RELATION_NOT_DEFINED" | "WINDOW_NOT_FINALIZED" | "MISSING_TELEMETRY" | "INSUFFICIENT_SAMPLES" | "TELEMETRY_GAP_EXCEEDED" | "BASELINE_NOT_STABLE" | "PROCESS_CHANGE_OUTSIDE_WINDOW" | "PROCESS_EFFECT_DIRECTION_MISMATCH" | "NO_PROCESS_CHANGE" | "CORRELATION_MATCH";
        /**
         * CorrelationStatus
         * @enum {string}
         */
        CorrelationStatus: "CORRELATED" | "NOT_CORRELATED" | "INSUFFICIENT_EVIDENCE" | "INDETERMINATE";
        /**
         * Criticality
         * @enum {string}
         */
        Criticality: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
        /** CyberPhysicalCorrelationFinding */
        CyberPhysicalCorrelationFinding: {
            /** Affected Process Points */
            affected_process_points: string[];
            /** Analyst Readable Explanation */
            analyst_readable_explanation: string;
            /** Anchor Time */
            anchor_time: string | null;
            /** Asset Context Evidence Id */
            asset_context_evidence_id: string | null;
            /** Asset Context Evidence Integrity Sha256 */
            asset_context_evidence_integrity_sha256: string | null;
            /**
             * Baseline Method
             * @constant
             */
            baseline_method: "FIXED_PRECEDING_WINDOW";
            /** Baseline Sample Count */
            baseline_sample_count: number;
            /**
             * Canonicalization Version
             * @constant
             */
            canonicalization_version: "otsoc-canonical-json-1";
            /**
             * Causality Inferred
             * @constant
             */
            causality_inferred: false;
            /** Configuration Hash */
            configuration_hash: string | null;
            /** Correlation End Time */
            correlation_end_time: string | null;
            /**
             * Correlation Id
             * Format: uuid
             */
            correlation_id: string;
            /**
             * Correlation Profile Id
             * @constant
             */
            correlation_profile_id: "otsoc.correlation.oil_gas_transfer";
            /** Correlation Profile Sha256 */
            correlation_profile_sha256: string;
            /** Correlation Profile Version */
            correlation_profile_version: string;
            /** Correlation Rule Id */
            correlation_rule_id: string;
            /** Correlation Rule Version */
            correlation_rule_version: string;
            /** Correlation Start Time */
            correlation_start_time: string | null;
            correlation_status: components["schemas"]["CorrelationStatus"];
            /**
             * Cyber Cause Asserted
             * @constant
             */
            cyber_cause_asserted: false;
            /**
             * Derivation Kind
             * @constant
             */
            derivation_kind: "CYBER_PHYSICAL_CORRELATION";
            /**
             * Domain
             * @constant
             */
            domain: "oil_gas_transfer";
            /** Effect Sample Count */
            effect_sample_count: number;
            /**
             * Evaluator Name
             * @constant
             */
            evaluator_name: "otsoc_offline_correlation_evaluator";
            /** Evaluator Version */
            evaluator_version: string;
            /**
             * Evidence Observed At
             * Format: date-time
             */
            evidence_observed_at: string;
            /**
             * Finding Schema
             * @constant
             */
            finding_schema: "otsoc.cyber_physical.correlation_finding";
            /**
             * Finding Schema Version
             * @constant
             */
            finding_schema_version: "1.0.0";
            /**
             * Ground Truth Used
             * @constant
             */
            ground_truth_used: false;
            /**
             * Malicious Intent Inferred
             * @constant
             */
            malicious_intent_inferred: false;
            /** Matched Minimum Set */
            matched_minimum_set: string | null;
            /** Maximum Gap Seconds */
            maximum_gap_seconds?: number | null;
            /** Observations */
            observations: components["schemas"]["PointObservation"][];
            /** Parent Set Sha256 */
            parent_set_sha256: string;
            /**
             * Policy Context Status
             * @enum {string}
             */
            policy_context_status: "APPROVED" | "DENIED" | "UNKNOWN" | "UNAVAILABLE";
            /** Policy Finding Evidence Id */
            policy_finding_evidence_id: string | null;
            /** Policy Finding Evidence Integrity Sha256 */
            policy_finding_evidence_integrity_sha256: string | null;
            /** Primary Cyber Evidence Id */
            primary_cyber_evidence_id: string | null;
            /** Primary Cyber Evidence Integrity Sha256 */
            primary_cyber_evidence_integrity_sha256: string | null;
            /** Process Assets */
            process_assets: components["schemas"]["ProcessAssetReference"][];
            /**
             * Process Model Version
             * @constant
             */
            process_model_version: "3.6";
            reason_code: components["schemas"]["CorrelationReasonCode"];
            /** Reevaluates Finding Id */
            reevaluates_finding_id: string | null;
            /** Run Origin */
            run_origin: string | null;
            /** Semantic Evidence Id */
            semantic_evidence_id: string | null;
            /** Semantic Evidence Integrity Sha256 */
            semantic_evidence_integrity_sha256: string | null;
            /** Simulation Id */
            simulation_id: string | null;
            /** Simulator Version */
            simulator_version: string | null;
            /** Statement Template Id */
            statement_template_id: string;
            /** Telemetry Parents */
            telemetry_parents: components["schemas"]["EvidenceParentReference"][];
            /** Telemetry Schema Version */
            telemetry_schema_version: string | null;
            /** Temporal Relation */
            temporal_relation: string;
            /**
             * Timestamp Authority
             * @constant
             */
            timestamp_authority: "OBSERVED_AT";
        };
        /**
         * DimensionStatus
         * @enum {string}
         */
        DimensionStatus: "SATISFIED" | "NOT_SATISFIED" | "UNKNOWN" | "NOT_APPLICABLE";
        /** EvidenceIngestRequest */
        EvidenceIngestRequest: {
            /**
             * Evidence Type
             * @constant
             */
            evidence_type: "simulator_telemetry";
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            payload: components["schemas"]["OilGasTelemetryPayloadV2"];
            /**
             * Payload Schema
             * @constant
             */
            payload_schema: "otsoc.simulator.telemetry";
            /**
             * Payload Schema Version
             * @constant
             */
            payload_schema_version: "2.0.0";
            provenance: components["schemas"]["EvidenceProvenance"];
            /** Sequence Number */
            sequence_number: number;
            /** Source Event Id */
            source_event_id: string;
            /** Source Key */
            source_key: string;
        };
        /** EvidenceIngestionReceipt */
        EvidenceIngestionReceipt: {
            /**
             * Evidence Id
             * Format: uuid
             */
            evidence_id: string;
            /**
             * Receipt Timestamp
             * Format: date-time
             */
            receipt_timestamp: string;
            /**
             * Schema Version
             * @default 1.0.0
             * @constant
             */
            schema_version: "1.0.0";
            /** Source Key */
            source_key: string;
            /**
             * Status
             * @enum {string}
             */
            status: "accepted" | "duplicate_existing";
        };
        /** EvidenceListResponse */
        EvidenceListResponse: {
            /** Evidence Type */
            evidence_type?: string | null;
            /** Items */
            items: components["schemas"]["EvidenceRecordResponse"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor?: string | null;
            /** Observed From */
            observed_from?: string | null;
            /** Observed To */
            observed_to?: string | null;
            /** Offset */
            offset: number;
            /** Source Key */
            source_key?: string | null;
        };
        /** EvidenceParentReference */
        EvidenceParentReference: {
            /**
             * Evidence Id
             * Format: uuid
             */
            evidence_id: string;
            /** Evidence Type */
            evidence_type: string;
            /** Integrity Sha256 */
            integrity_sha256: string;
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /** Sequence Number */
            sequence_number?: number | null;
        };
        /** EvidenceProvenance */
        EvidenceProvenance: {
            /** Configuration Hash */
            configuration_hash: string;
            /**
             * Domain
             * @constant
             */
            domain: "oil_gas_transfer";
            /**
             * Producer
             * @constant
             */
            producer: "otsoc_simulator";
            /**
             * Producer Version
             * @constant
             */
            producer_version: "3.0.0";
            /** Seed */
            seed: number;
            /** Simulation Id */
            simulation_id: string;
        };
        /** EvidenceRecordResponse */
        EvidenceRecordResponse: {
            /** Canonical Byte Length */
            canonical_byte_length: number;
            /**
             * Evidence Id
             * Format: uuid
             */
            evidence_id: string;
            /** Evidence Type */
            evidence_type: string;
            /** Evidence Version */
            evidence_version: number;
            /** Integrity Sha256 */
            integrity_sha256: string;
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /** Payload */
            payload: components["schemas"]["HistoricalCoolingTelemetryPayloadV1"] | components["schemas"]["OilGasTelemetryPayloadV2"] | components["schemas"]["SyntheticModbusEvent"] | components["schemas"]["ProtocolSemanticEvent"] | components["schemas"]["AssetContextEvent"] | components["schemas"]["CommunicationPolicyFinding"] | components["schemas"]["CyberPhysicalCorrelationFinding"];
            /** Payload Schema */
            payload_schema: string;
            /**
             * Payload Schema Version
             * @enum {string}
             */
            payload_schema_version: "1.0.0" | "2.0.0";
            /** Provenance */
            provenance: components["schemas"]["HistoricalEvidenceProvenanceV1"] | components["schemas"]["EvidenceProvenance"] | components["schemas"]["SyntheticProtocolProvenance"] | components["schemas"]["SemanticDerivationProvenance"] | components["schemas"]["AssetContextDerivationProvenance"] | components["schemas"]["PolicyFindingDerivationProvenance"] | components["schemas"]["CorrelationDerivationProvenance"];
            /**
             * Received At
             * Format: date-time
             */
            received_at: string;
            /** Sequence Number */
            sequence_number: number | null;
            /** Source Event Id */
            source_event_id: string;
            /** Source Key */
            source_key: string;
        };
        /**
         * EvidenceRole
         * @enum {string}
         */
        EvidenceRole: "PRIMARY" | "SUPPORTING" | "CONTRADICTING" | "CONTEXT";
        /**
         * FunctionSemantic
         * @enum {string}
         */
        FunctionSemantic: "READ_DISCRETE_INPUTS" | "READ_HOLDING_REGISTERS" | "READ_INPUT_REGISTERS" | "WRITE_SINGLE_REGISTER";
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * HistoricalCoolingTelemetryPayloadV1
         * @description Read-only compatibility model for accepted historical cooling evidence.
         */
        HistoricalCoolingTelemetryPayloadV1: {
            /** Configuration Hash */
            configuration_hash: string;
            /** Flow Rate M3H */
            flow_rate_m3h: number;
            /** Inlet Temperature C */
            inlet_temperature_c: number;
            /** Outlet Temperature C */
            outlet_temperature_c: number;
            /** Pressure Bar */
            pressure_bar: number;
            /** Pump Command Percent */
            pump_command_percent: number;
            /** Pump Running */
            pump_running: boolean;
            /** Sequence Number */
            sequence_number: number;
            /** Simulation Id */
            simulation_id: string;
            /** Simulation Time Seconds */
            simulation_time_seconds: number;
            /** Simulator Version */
            simulator_version: string;
            /** Tank Level Percent */
            tank_level_percent: number;
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
        };
        /** HistoricalEvidenceProvenanceV1 */
        HistoricalEvidenceProvenanceV1: {
            /** Configuration Hash */
            configuration_hash: string;
            /**
             * Producer
             * @constant
             */
            producer: "otsoc_simulator";
            /** Producer Version */
            producer_version: string;
            /** Simulation Id */
            simulation_id: string;
        };
        /** Identifier */
        Identifier: {
            identifier_type: components["schemas"]["IdentifierType"];
            /** Value */
            value: string;
        };
        /**
         * IdentifierType
         * @enum {string}
         */
        IdentifierType: "LOGICAL_ID" | "PROTOCOL_ENDPOINT_ID" | "PROCESS_TAG";
        /** IdentityClaim */
        IdentityClaim: {
            identifier_type: components["schemas"]["IdentifierType"];
            /** Value */
            value: string;
        };
        /** IncidentAssignmentPatchRequest */
        IncidentAssignmentPatchRequest: {
            /** Assignee User Id */
            assignee_user_id: string | null;
            /** Expected Version */
            expected_version: number;
        };
        /** IncidentAuditListResponse */
        IncidentAuditListResponse: {
            /** Items */
            items: components["schemas"]["IncidentAuditResponse"][];
        };
        /** IncidentAuditResponse */
        IncidentAuditResponse: {
            /** Action */
            action: string;
            /** Actor Display Name */
            actor_display_name: string;
            /** Actor User Id */
            actor_user_id: string | null;
            /**
             * Audit Id
             * Format: uuid
             */
            audit_id: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Request Id */
            request_id: string;
            /** Result */
            result: string;
            /** Summary */
            summary: string;
        };
        /**
         * IncidentCategory
         * @enum {string}
         */
        IncidentCategory: "ASSET_IDENTITY_ANOMALY" | "COMMUNICATION_POLICY_VIOLATION" | "CONTROL_COMMAND_INVESTIGATION" | "PROCESS_INCONSISTENCY";
        /** IncidentCategorySummary */
        IncidentCategorySummary: {
            /** Asset Identity Anomaly */
            asset_identity_anomaly: number;
            /** Communication Policy Violation */
            communication_policy_violation: number;
            /** Control Command Investigation */
            control_command_investigation: number;
            /** Process Inconsistency */
            process_inconsistency: number;
        };
        /** IncidentContextResponse */
        IncidentContextResponse: {
            /** Correlation */
            correlation: string;
            /** Evidence Completeness */
            evidence_completeness: string;
            /** Policy */
            policy: string;
            /** Unavailable */
            unavailable: string[];
        };
        /** IncidentDetailResponse */
        IncidentDetailResponse: {
            context: components["schemas"]["IncidentContextResponse"];
            /** Evidence Memberships */
            evidence_memberships: components["schemas"]["IncidentMembershipResponse"][];
            incident: components["schemas"]["IncidentRecordResponse"];
            /** Lineage References */
            lineage_references: components["schemas"]["IncidentLineageReference"][];
            /** Notes */
            notes: components["schemas"]["IncidentNoteResponse"][];
            /** Severity History */
            severity_history: components["schemas"]["IncidentSeverityHistoryResponse"][];
            /** Status History */
            status_history: components["schemas"]["IncidentStatusHistoryResponse"][];
            /** Timeline */
            timeline: components["schemas"]["IncidentTimelineResponse"][];
        };
        /**
         * IncidentDisposition
         * @enum {string}
         */
        IncidentDisposition: "UNREVIEWED" | "TRUE_POSITIVE" | "FALSE_POSITIVE";
        /** IncidentDispositionPatchRequest */
        IncidentDispositionPatchRequest: {
            disposition: components["schemas"]["IncidentDisposition"];
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
        };
        /** IncidentLineageReference */
        IncidentLineageReference: {
            /**
             * Evidence Id
             * Format: uuid
             */
            evidence_id: string;
            /** Evidence Type */
            evidence_type: string;
            /** Integrity Sha256 */
            integrity_sha256: string;
            /** Relationship */
            relationship: string;
        };
        /** IncidentListResponse */
        IncidentListResponse: {
            /** Items */
            items: components["schemas"]["IncidentRecordResponse"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** IncidentMembershipResponse */
        IncidentMembershipResponse: {
            /**
             * Added At
             * Format: date-time
             */
            added_at: string;
            /**
             * Evidence Id
             * Format: uuid
             */
            evidence_id: string;
            /** Evidence Schema */
            evidence_schema: string;
            /** Evidence Schema Version */
            evidence_schema_version: string;
            /** Evidence Type */
            evidence_type: string;
            /** Integrity Sha256 */
            integrity_sha256: string;
            /**
             * Membership Id
             * Format: uuid
             */
            membership_id: string;
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /**
             * Received At
             * Format: date-time
             */
            received_at: string;
            role: components["schemas"]["EvidenceRole"];
        };
        /** IncidentMutationResponse */
        IncidentMutationResponse: {
            incident: components["schemas"]["IncidentRecordResponse"];
            /**
             * Operation
             * @enum {string}
             */
            operation: "status_changed" | "note_added" | "assignment_changed" | "disposition_changed";
            /**
             * Warnings
             * @default []
             */
            warnings: string[];
        };
        /** IncidentNoteCreateRequest */
        IncidentNoteCreateRequest: {
            /** Content */
            content: string;
            /** Expected Version */
            expected_version: number;
        };
        /** IncidentNoteResponse */
        IncidentNoteResponse: {
            /** Actor Context */
            actor_context: string;
            /** Actor User Id */
            actor_user_id?: string | null;
            /** Aggregate Version */
            aggregate_version: number;
            /** Content */
            content: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Note Id
             * Format: uuid
             */
            note_id: string;
        };
        /** IncidentOverviewSummary */
        IncidentOverviewSummary: {
            categories: components["schemas"]["IncidentCategorySummary"];
            /** High */
            high: number;
            /** High Non Resolved */
            high_non_resolved: number;
            /** Investigating */
            investigating: number;
            /** Low */
            low: number;
            /** Medium */
            medium: number;
            /** Open */
            open: number;
            /** Resolved */
            resolved: number;
            /** Total */
            total: number;
        };
        /** IncidentRecordResponse */
        IncidentRecordResponse: {
            /** Assigned At */
            assigned_at: string | null;
            /** Assignee Display Name */
            assignee_display_name?: string | null;
            /** Assignee User Id */
            assignee_user_id: string | null;
            /** Bound Configuration Hash */
            bound_configuration_hash: string | null;
            /** Bound Simulation Id */
            bound_simulation_id: string | null;
            category: components["schemas"]["IncidentCategory"];
            /**
             * Causality Inferred
             * @constant
             */
            causality_inferred: false;
            /** Configuration Scope */
            configuration_scope: string;
            /** Controller Asset Id */
            controller_asset_id: string | null;
            /** Correlation Context */
            correlation_context: string;
            /** Correlation Rule Id */
            correlation_rule_id: string | null;
            /** Correlation Rule Version */
            correlation_rule_version: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Destination Asset Id */
            destination_asset_id: string | null;
            disposition: components["schemas"]["IncidentDisposition"];
            /** Disposition Reason */
            disposition_reason: string | null;
            /** Disposition Set At */
            disposition_set_at: string | null;
            /** Disposition Set By User Id */
            disposition_set_by_user_id: string | null;
            /** Evidence Completeness */
            evidence_completeness: string;
            /** Evidence Count */
            evidence_count: number;
            /**
             * First Observed At
             * Format: date-time
             */
            first_observed_at: string;
            /**
             * Ground Truth Used
             * @constant
             */
            ground_truth_used: false;
            /**
             * Grouping Epoch Start
             * Format: date-time
             */
            grouping_epoch_start: string;
            /** Grouping Key Sha256 */
            grouping_key_sha256: string;
            /**
             * Incident Id
             * Format: uuid
             */
            incident_id: string;
            /**
             * Incident Profile Id
             * @constant
             */
            incident_profile_id: "otsoc.incident.oil_gas_transfer";
            /** Incident Profile Sha256 */
            incident_profile_sha256: string;
            /**
             * Incident Profile Version
             * @constant
             */
            incident_profile_version: "1.0.0";
            /**
             * Incident Schema
             * @constant
             */
            incident_schema: "otsoc.incident.record";
            /**
             * Incident Schema Version
             * @constant
             */
            incident_schema_version: "1.0.0";
            /**
             * Last Observed At
             * Format: date-time
             */
            last_observed_at: string;
            /**
             * Malicious Intent Inferred
             * @constant
             */
            malicious_intent_inferred: false;
            /** Policy Context */
            policy_context: string;
            /**
             * Primary Evidence Id
             * Format: uuid
             */
            primary_evidence_id: string;
            /** Primary Evidence Integrity Sha256 */
            primary_evidence_integrity_sha256: string;
            /** Primary Evidence Schema */
            primary_evidence_schema: string;
            /** Primary Evidence Schema Version */
            primary_evidence_schema_version: string;
            /** Primary Evidence Type */
            primary_evidence_type: string;
            /** Process Asset Ids */
            process_asset_ids: string[];
            /** Process Asset Keys */
            process_asset_keys: string[];
            /** Qualification Rule Id */
            qualification_rule_id: string;
            /**
             * Qualification Rule Version
             * @constant
             */
            qualification_rule_version: "1.0.0";
            /** Run Id */
            run_id?: string | null;
            /** Run Scope */
            run_scope: string;
            /** S3 Semantic Evidence Id */
            s3_semantic_evidence_id: string | null;
            /** Scenario Id */
            scenario_id?: ("BASELINE" | "S1" | "S2" | "S3" | "S4") | null;
            severity: components["schemas"]["IncidentSeverity"];
            /** Source Asset Id */
            source_asset_id: string | null;
            status: components["schemas"]["IncidentStatus"];
            /** Summary */
            summary: string;
            /** Target Point Ids */
            target_point_ids: string[];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
        };
        /** IncidentReportAutoContext */
        IncidentReportAutoContext: {
            /** Affected Assets */
            affected_assets: string[];
            /** Assignee User Id */
            assignee_user_id: string | null;
            category: components["schemas"]["IncidentCategory"];
            /** Correlation Context */
            correlation_context: string;
            disposition: components["schemas"]["IncidentDisposition"];
            /** Evidence Count */
            evidence_count: number;
            /**
             * First Observed At
             * Format: date-time
             */
            first_observed_at: string;
            /**
             * Incident Id
             * Format: uuid
             */
            incident_id: string;
            /**
             * Last Observed At
             * Format: date-time
             */
            last_observed_at: string;
            /** Policy Context */
            policy_context: string;
            /** Process Context */
            process_context: string;
            /** Protocol Context */
            protocol_context: string;
            severity: components["schemas"]["IncidentSeverity"];
            status: components["schemas"]["IncidentStatus"];
        };
        /** IncidentReportPutRequest */
        IncidentReportPutRequest: {
            /**
             * Analyst Assessment
             * @default
             */
            analyst_assessment: string;
            /**
             * Disposition Rationale
             * @default
             */
            disposition_rationale: string;
            /**
             * Evidence Assessment
             * @default
             */
            evidence_assessment: string;
            /** Expected Version */
            expected_version: number;
            /**
             * Final Conclusion
             * @default
             */
            final_conclusion: string;
            /**
             * Investigation Summary
             * @default
             */
            investigation_summary: string;
            /**
             * Process Impact Assessment
             * @default
             */
            process_impact_assessment: string;
            /**
             * Recommended Follow Up
             * @default
             */
            recommended_follow_up: string;
        };
        /** IncidentReportResponse */
        IncidentReportResponse: {
            /**
             * Analyst Assessment
             * @default
             */
            analyst_assessment: string;
            auto_context: components["schemas"]["IncidentReportAutoContext"];
            /** Created At */
            created_at: string | null;
            /** Created By User Id */
            created_by_user_id: string | null;
            /**
             * Disposition Rationale
             * @default
             */
            disposition_rationale: string;
            /**
             * Evidence Assessment
             * @default
             */
            evidence_assessment: string;
            /** Fields Filled */
            fields_filled: number;
            /**
             * Fields Total
             * @default 7
             * @constant
             */
            fields_total: 7;
            /**
             * Final Conclusion
             * @default
             */
            final_conclusion: string;
            /**
             * Incident Id
             * Format: uuid
             */
            incident_id: string;
            /**
             * Investigation Summary
             * @default
             */
            investigation_summary: string;
            /**
             * Process Impact Assessment
             * @default
             */
            process_impact_assessment: string;
            /**
             * Recommended Follow Up
             * @default
             */
            recommended_follow_up: string;
            /** Updated At */
            updated_at: string | null;
            /** Updated By User Id */
            updated_by_user_id: string | null;
            /** Version */
            version: number;
        };
        /**
         * IncidentSeverity
         * @enum {string}
         */
        IncidentSeverity: "LOW" | "MEDIUM" | "HIGH";
        /** IncidentSeverityHistoryResponse */
        IncidentSeverityHistoryResponse: {
            /** Aggregate Version */
            aggregate_version: number;
            /**
             * Calculated At
             * Format: date-time
             */
            calculated_at: string;
            new_severity: components["schemas"]["IncidentSeverity"];
            previous_severity: components["schemas"]["IncidentSeverity"] | null;
            /** Profile Version */
            profile_version: string;
            /** Rule Version */
            rule_version: string;
            /**
             * Severity History Id
             * Format: uuid
             */
            severity_history_id: string;
            /**
             * Triggering Evidence Id
             * Format: uuid
             */
            triggering_evidence_id: string;
            /** Triggering Integrity Sha256 */
            triggering_integrity_sha256: string;
        };
        /**
         * IncidentStatus
         * @enum {string}
         */
        IncidentStatus: "OPEN" | "INVESTIGATING" | "RESOLVED";
        /** IncidentStatusHistoryResponse */
        IncidentStatusHistoryResponse: {
            /** Actor Context */
            actor_context: string;
            /** Actor User Id */
            actor_user_id?: string | null;
            /**
             * Changed At
             * Format: date-time
             */
            changed_at: string;
            new_status: components["schemas"]["IncidentStatus"];
            previous_status: components["schemas"]["IncidentStatus"] | null;
            /** Reason */
            reason: string | null;
            /** Request Id */
            request_id: string;
            /**
             * Status History Id
             * Format: uuid
             */
            status_history_id: string;
            /** Version After */
            version_after: number;
            /** Version Before */
            version_before: number;
        };
        /** IncidentStatusPatchRequest */
        IncidentStatusPatchRequest: {
            /** Expected Version */
            expected_version: number;
            new_status: components["schemas"]["IncidentStatus"];
            /** Reason */
            reason?: string | null;
        };
        /** IncidentTimelineResponse */
        IncidentTimelineResponse: {
            /** Actor Context */
            actor_context: string;
            /** Aggregate Version */
            aggregate_version: number;
            /** Asset Ids */
            asset_ids: string[];
            entry_type: components["schemas"]["TimelineEntryType"];
            /** Evidence Id */
            evidence_id: string | null;
            /** Evidence Integrity Sha256 */
            evidence_integrity_sha256: string | null;
            /** Evidence Schema */
            evidence_schema: string | null;
            /** Evidence Schema Version */
            evidence_schema_version: string | null;
            /** Evidence Type */
            evidence_type: string | null;
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /** Process Asset Ids */
            process_asset_ids: string[];
            /** Received At */
            received_at: string | null;
            /**
             * Recorded At
             * Format: date-time
             */
            recorded_at: string;
            /**
             * Reference Id
             * Format: uuid
             */
            reference_id: string;
            /** Summary */
            summary: string;
            /**
             * Timeline Entry Id
             * Format: uuid
             */
            timeline_entry_id: string;
        };
        /**
         * InterpretationStatus
         * @enum {string}
         */
        InterpretationStatus: "MAPPED" | "UNMAPPED" | "UNSUPPORTED" | "MALFORMED";
        /**
         * LabActivationReason
         * @enum {string}
         */
        LabActivationReason: "STARTUP_BASELINE" | "SCENARIO_COMPLETED" | "RETURN_BASELINE" | "RESET";
        /** LabCatalogResponse */
        LabCatalogResponse: {
            /**
             * Dataset Id
             * @constant
             */
            dataset_id: "otsoc.final-evaluation.oil-gas-transfer";
            /** Dataset Sha256 */
            dataset_sha256: string;
            /**
             * Dataset Version
             * @constant
             */
            dataset_version: "1.0.0";
            /** Items */
            items: components["schemas"]["LabScenarioCatalogItem"][];
        };
        /** LabContextResponse */
        LabContextResponse: {
            activation_reason: components["schemas"]["LabActivationReason"];
            active_run: components["schemas"]["LabRunResponse"];
            /**
             * Changed At
             * Format: date-time
             */
            changed_at: string;
            /** Changed By Actor */
            changed_by_actor: string;
            /** Changed By User Id */
            changed_by_user_id: string | null;
            /** Context Version */
            context_version: number;
        };
        /**
         * LabNoFieldsRequest
         * @description Optional empty body contract for lab mutations that accept no controls.
         */
        LabNoFieldsRequest: Record<string, never>;
        /** LabRunListResponse */
        LabRunListResponse: {
            /** Items */
            items: components["schemas"]["LabRunResponse"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /** LabRunResponse */
        LabRunResponse: {
            /** Completed At */
            completed_at: string | null;
            /** Configuration Hash */
            configuration_hash: string | null;
            /** Configuration Id */
            configuration_id: string | null;
            /** Dataset Case Id */
            dataset_case_id: string;
            /**
             * Dataset Id
             * @constant
             */
            dataset_id: "otsoc.final-evaluation.oil-gas-transfer";
            /** Dataset Sha256 */
            dataset_sha256: string;
            /**
             * Dataset Version
             * @constant
             */
            dataset_version: "1.0.0";
            /**
             * Definition Version
             * @constant
             */
            definition_version: "1.0.0";
            /** Evidence Count */
            evidence_count: number;
            /** Failure Code */
            failure_code: string | null;
            /** Incident Count */
            incident_count: number;
            /** Incident Ids */
            incident_ids: string[];
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            scenario_id: components["schemas"]["LabScenarioId"];
            /** Scenario Title */
            scenario_title: string;
            /** Simulation Id */
            simulation_id: string | null;
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            /** Started By */
            started_by: string | null;
            /** Started By Display Name */
            started_by_display_name: string;
            /** Started By User Id */
            started_by_user_id: string | null;
            status: components["schemas"]["LabRunState"];
            /** Window End */
            window_end: string | null;
            /** Window Start */
            window_start: string | null;
        };
        /** LabRunStartRequest */
        LabRunStartRequest: {
            scenario_id: components["schemas"]["LabScenarioId"];
        };
        /**
         * LabRunState
         * @enum {string}
         */
        LabRunState: "RUNNING" | "COMPLETED" | "FAILED";
        /** LabScenarioCatalogItem */
        LabScenarioCatalogItem: {
            /** Dataset Case Id */
            dataset_case_id: string;
            /**
             * Definition Version
             * @constant
             */
            definition_version: "1.0.0";
            /** Description */
            description: string;
            /**
             * Execution Mode
             * @constant
             */
            execution_mode: "FROZEN_DETERMINISTIC_PIPELINE";
            scenario_id: components["schemas"]["LabScenarioId"];
            /**
             * State
             * @default READY
             * @constant
             */
            state: "READY";
            /**
             * Synthetic
             * @constant
             */
            synthetic: true;
            /** Title */
            title: string;
        };
        /**
         * LabScenarioId
         * @enum {string}
         */
        LabScenarioId: "BASELINE" | "S1" | "S2" | "S3" | "S4";
        /** LabStartResponse */
        LabStartResponse: {
            active_run: components["schemas"]["LabRunResponse"];
            run: components["schemas"]["LabRunResponse"];
        };
        /** LivenessResponse */
        LivenessResponse: {
            /** Service */
            service: string;
            /**
             * Status
             * @constant
             */
            status: "ok";
            /** Version */
            version: string;
        };
        /**
         * LogicalType
         * @enum {string}
         */
        LogicalType: "decimal" | "boolean";
        /** LoginRequest */
        LoginRequest: {
            /**
             * Password
             * Format: password
             */
            password: string;
            /** Username */
            username: string;
        };
        /**
         * MessageRole
         * @enum {string}
         */
        MessageRole: "REQUEST" | "RESPONSE" | "OPERATION";
        /** MetadataResponse */
        MetadataResponse: {
            /** Active Profiles */
            active_profiles: components["schemas"]["ActiveProfileMetadata"][];
            /** Active Schemas */
            active_schemas: components["schemas"]["ActiveSchemaMetadata"][];
            /** Api Version */
            api_version: string;
            /** Application Name */
            application_name: string;
            /** Application Version */
            application_version: string;
            /**
             * Domain
             * @constant
             */
            domain: "oil_gas_transfer";
            /** Environment */
            environment: string;
            /**
             * Operating Mode
             * @constant
             */
            operating_mode: "SYNTHETIC_OFFLINE";
        };
        /**
         * ObservationRole
         * @enum {string}
         */
        ObservationRole: "REQUIRED" | "SUPPORTING" | "CONTRADICTING";
        /** OilGasTelemetryPayloadV2 */
        OilGasTelemetryPayloadV2: {
            /** Configuration Hash */
            configuration_hash: string;
            /** Control Valve Position Percent */
            control_valve_position_percent: number;
            /**
             * Domain
             * @constant
             */
            domain: "oil_gas_transfer";
            /** Pipeline Flow Rate M3H */
            pipeline_flow_rate_m3h: number;
            /** Pipeline Pressure Bar */
            pipeline_pressure_bar: number;
            /** Process Temperature C */
            process_temperature_c: number;
            /** Receiving Tank Level Percent */
            receiving_tank_level_percent: number;
            /** Sequence Number */
            sequence_number: number;
            /** Simulation Id */
            simulation_id: string;
            /** Simulation Time Seconds */
            simulation_time_seconds: number;
            /**
             * Simulator Version
             * @constant
             */
            simulator_version: "3.0.0";
            /** Source Tank Level Percent */
            source_tank_level_percent: number;
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
            /** Transfer Pump Command Percent */
            transfer_pump_command_percent: number;
            /** Transfer Pump Running */
            transfer_pump_running: boolean;
        };
        /**
         * OperationCategory
         * @enum {string}
         */
        OperationCategory: "READ" | "WRITE" | "UNSUPPORTED";
        /**
         * OperationCompatibility
         * @enum {string}
         */
        OperationCompatibility: "COMPATIBLE" | "INCOMPATIBLE" | "NOT_APPLICABLE";
        /** OverviewRunContext */
        OverviewRunContext: {
            /** Configuration Hash */
            configuration_hash: string | null;
            /**
             * Context Scope
             * @constant
             */
            context_scope: "CURRENT_RUN";
            /** Evidence Simulation Id */
            evidence_simulation_id: string | null;
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            /**
             * Scenario Id
             * @enum {string}
             */
            scenario_id: "BASELINE" | "S1" | "S2" | "S3" | "S4";
            /**
             * Scenario State
             * @constant
             */
            scenario_state: "COMPLETED";
        };
        /** OverviewSummaryResponse */
        OverviewSummaryResponse: {
            active_run: components["schemas"]["OverviewRunContext"];
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            assets: components["schemas"]["AssetOverviewSummary"];
            correlations: components["schemas"]["CorrelationOverviewSummary"];
            /**
             * Generated At
             * Format: date-time
             */
            generated_at: string;
            incidents: components["schemas"]["IncidentOverviewSummary"];
            linked_valve_command: components["schemas"]["EvidenceRecordResponse"] | null;
            policy_findings: components["schemas"]["PolicyOverviewSummary"];
            process_snapshot: components["schemas"]["EvidenceRecordResponse"] | null;
            /** Process Snapshot Message */
            process_snapshot_message: string;
            /**
             * Process Snapshot Scope
             * @enum {string}
             */
            process_snapshot_scope: "ACTIVE_RUN" | "BASELINE_REFERENCE" | "UNAVAILABLE";
            /**
             * Process Snapshot Status
             * @enum {string}
             */
            process_snapshot_status: "COMPLETE" | "UNAVAILABLE";
            /** Recent Activity */
            recent_activity: components["schemas"]["RecentActivity"][];
            /**
             * Window Complete
             * @constant
             */
            window_complete: true;
            /**
             * Window End
             * Format: date-time
             */
            window_end: string;
            /**
             * Window Start
             * Format: date-time
             */
            window_start: string;
        };
        /** PasswordResetRequest */
        PasswordResetRequest: {
            /** Expected Version */
            expected_version: number;
            /**
             * Password
             * Format: password
             */
            password: string;
        };
        /**
         * PointAccessClass
         * @enum {string}
         */
        PointAccessClass: "READ_ONLY" | "COMMANDABLE_SYNTHETIC";
        /** PointObservation */
        PointObservation: {
            /** Asset Key */
            asset_key: string;
            /** Baseline Value */
            baseline_value: number | boolean | null;
            /** Condition Met */
            condition_met: boolean;
            /** Delta */
            delta: number | null;
            expected_direction: components["schemas"]["ProcessChange"];
            observed_direction: components["schemas"]["ProcessChange"];
            /** Observed Value */
            observed_value: number | boolean | null;
            /** Persistence Observed */
            persistence_observed: number;
            /** Persistence Required */
            persistence_required: number;
            /** Point Id */
            point_id: string;
            role: components["schemas"]["ObservationRole"];
            /** Threshold */
            threshold: number | null;
            /** Unit */
            unit: string;
        };
        /** PolicyFindingDerivationProvenance */
        PolicyFindingDerivationProvenance: {
            /**
             * Asset Context Event Id
             * Format: uuid
             */
            asset_context_event_id: string;
            /** Asset Context Integrity Sha256 */
            asset_context_integrity_sha256: string;
            /**
             * Canonicalization Version
             * @constant
             */
            canonicalization_version: "otsoc-canonical-json-1";
            /**
             * Derivation Kind
             * @constant
             */
            derivation_kind: "COMMUNICATION_POLICY_EVALUATION";
            /**
             * Educational Only
             * @constant
             */
            educational_only: true;
            /**
             * Evaluator Name
             * @constant
             */
            evaluator_name: "otsoc_communication_policy_evaluator";
            /** Evaluator Version */
            evaluator_version: string;
            /**
             * Ground Truth Used
             * @constant
             */
            ground_truth_used: false;
            /**
             * Inventory Profile
             * @constant
             */
            inventory_profile: "otsoc.asset_inventory.oil_gas_transfer";
            /** Inventory Sha256 */
            inventory_sha256: string;
            /** Inventory Version */
            inventory_version: string;
            /**
             * Policy Profile
             * @constant
             */
            policy_profile: "otsoc.communication_policy.oil_gas_transfer";
            /** Policy Sha256 */
            policy_sha256: string;
            /** Policy Version */
            policy_version: string;
            /**
             * Semantic Event Id
             * Format: uuid
             */
            semantic_event_id: string;
            /** Semantic Evidence Integrity Sha256 */
            semantic_evidence_integrity_sha256: string;
            /**
             * Source Evidence Id
             * Format: uuid
             */
            source_evidence_id: string;
        };
        /** PolicyOverviewSummary */
        PolicyOverviewSummary: {
            /** Approved */
            approved: number;
            /** Denied */
            denied: number;
            /** Total */
            total: number;
            /** Unknown */
            unknown: number;
        };
        /**
         * PolicyReasonCode
         * @enum {string}
         */
        PolicyReasonCode: "SOURCE_EVIDENCE_NOT_VERIFIED" | "SEMANTIC_EVIDENCE_NOT_VERIFIED" | "PROFILE_VERSION_UNSUPPORTED" | "POLICY_PROFILE_INVALID" | "IDENTITY_CONFLICT" | "SOURCE_UNKNOWN" | "DESTINATION_UNKNOWN" | "SOURCE_DISABLED" | "DESTINATION_DISABLED" | "SOURCE_ZONE_UNEXPECTED" | "DESTINATION_ZONE_UNEXPECTED" | "POINT_WRITE_NOT_APPROVED" | "PROTOCOL_NOT_APPROVED" | "OPERATION_NOT_APPROVED" | "SOURCE_ROLE_NOT_APPROVED" | "COMMUNICATION_NOT_APPROVED" | "POLICY_NOT_CLASSIFIED" | "POLICY_MATCH_APPROVED";
        /**
         * PolicyStatus
         * @enum {string}
         */
        PolicyStatus: "APPROVED" | "DENIED" | "UNKNOWN";
        /** ProcessAssetReference */
        ProcessAssetReference: {
            /**
             * Asset Id
             * Format: uuid
             */
            asset_id: string;
            /** Asset Key */
            asset_key: string;
        };
        /**
         * ProcessChange
         * @enum {string}
         */
        ProcessChange: "INCREASED" | "DECREASED" | "UNCHANGED" | "UNAVAILABLE";
        /** ProductAsset */
        ProductAsset: {
            /**
             * Asset Id
             * Format: uuid
             */
            asset_id: string;
            definition: components["schemas"]["AssetDefinition"];
            /** Process Point Ids */
            process_point_ids: string[];
        };
        /** ProtocolSemanticEvent */
        ProtocolSemanticEvent: {
            canonical_address: components["schemas"]["CanonicalAddress"];
            /**
             * Canonicalization Version
             * @constant
             */
            canonicalization_version: "otsoc-canonical-json-1";
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Decoded Value */
            decoded_value: string | boolean | null;
            /**
             * Decoder Name
             * @constant
             */
            decoder_name: "otsoc_offline_modbus_semantics";
            /** Decoder Version */
            decoder_version: string;
            /**
             * Derivation Kind
             * @constant
             */
            derivation_kind: "SEMANTIC_INTERPRETATION";
            /**
             * Derived From
             * Format: uuid
             */
            derived_from: string;
            /** Destination Identity */
            destination_identity: string;
            /** Fictional Target Component */
            fictional_target_component: string | null;
            /** Function Code */
            function_code: number;
            function_semantic: components["schemas"]["FunctionSemantic"] | null;
            /**
             * Ground Truth Used
             * @constant
             */
            ground_truth_used: false;
            interpretation_status: components["schemas"]["InterpretationStatus"];
            logical_type: components["schemas"]["LogicalType"] | null;
            message_role: components["schemas"]["MessageRole"];
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            operation_category: components["schemas"]["OperationCategory"];
            operation_compatibility: components["schemas"]["OperationCompatibility"];
            point_access_class: components["schemas"]["PointAccessClass"] | null;
            /** Point Id */
            point_id: string | null;
            /**
             * Profile Id
             * @constant
             */
            profile_id: "otsoc.synthetic_modbus.oil_gas_transfer";
            /** Profile Sha256 */
            profile_sha256: string;
            /**
             * Profile Version
             * @constant
             */
            profile_version: "1.0.0";
            /**
             * Protocol
             * @constant
             */
            protocol: "modbus_tcp";
            /** Raw Value */
            raw_value: number | string | boolean | null;
            reason_code: components["schemas"]["ReasonCode"];
            /**
             * Semantic Event Id
             * Format: uuid
             */
            semantic_event_id: string;
            /**
             * Semantic Schema
             * @constant
             */
            semantic_schema: "otsoc.protocol.semantic_event";
            /**
             * Semantic Schema Version
             * @constant
             */
            semantic_schema_version: "1.0.0";
            /** Semantic Statement */
            semantic_statement: string;
            /**
             * Source Evidence Id
             * Format: uuid
             */
            source_evidence_id: string;
            /** Source Evidence Integrity Sha256 */
            source_evidence_integrity_sha256: string;
            /** Source Identity */
            source_identity: string;
            /** Statement Template Id */
            statement_template_id: string;
            /** Transaction Id */
            transaction_id: number;
            /** Unit */
            unit: string | null;
            /** Unit Id */
            unit_id: number;
        };
        /** ReadinessResponse */
        ReadinessResponse: {
            /**
             * Database
             * @enum {string}
             */
            database: "available" | "unavailable";
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "unavailable";
        };
        /**
         * ReasonCode
         * @enum {string}
         */
        ReasonCode: "NONE" | "ADDRESS_NOT_IN_PROFILE" | "ADDRESS_INVALID" | "FUNCTION_NOT_SUPPORTED" | "FUNCTION_TABLE_MISMATCH" | "POINT_NOT_COMMANDABLE" | "RAW_VALUE_REQUIRED" | "RAW_VALUE_TYPE_INVALID" | "RAW_VALUE_OUT_OF_UINT16_RANGE" | "ENGINEERING_VALUE_OUT_OF_RANGE" | "PROTOCOL_ID_INVALID" | "SOURCE_EVIDENCE_NOT_VERIFIED" | "PROFILE_DIGEST_MISMATCH";
        /** RecentActivity */
        RecentActivity: {
            /**
             * Activity Id
             * Format: uuid
             */
            activity_id: string;
            /** Asset Ids */
            asset_ids: string[];
            /** Entry Type */
            entry_type: string;
            /**
             * Incident Id
             * Format: uuid
             */
            incident_id: string;
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /** Summary */
            summary: string;
        };
        /** RelationshipDefinition */
        RelationshipDefinition: {
            relationship_type: components["schemas"]["RelationshipType"];
            /** Source Asset Key */
            source_asset_key: string;
            target_kind: components["schemas"]["RelationshipTargetKind"];
            /** Target Ref */
            target_ref: string;
        };
        /**
         * RelationshipTargetKind
         * @enum {string}
         */
        RelationshipTargetKind: "ASSET" | "ENDPOINT";
        /**
         * RelationshipType
         * @enum {string}
         */
        RelationshipType: "HOSTS_ENDPOINT" | "CONTROLS" | "OBSERVES" | "MONITORS";
        /** ReplayBundleResponse */
        ReplayBundleResponse: {
            /**
             * Completeness
             * @enum {string}
             */
            completeness: "COMPLETE" | "PARTIAL";
            /** Configuration Hash */
            configuration_hash: string | null;
            /** Correlation Evidence Id */
            correlation_evidence_id: string | null;
            /** Events */
            events: components["schemas"]["ReplayEvent"][];
            /** Gaps */
            gaps: string[];
            incident: components["schemas"]["IncidentRecordResponse"] | null;
            /** Lab Run Id */
            lab_run_id?: string | null;
            /** Observed From */
            observed_from: string | null;
            /** Observed To */
            observed_to: string | null;
            /** Scenario Id */
            scenario_id?: ("BASELINE" | "S1" | "S2" | "S3" | "S4") | null;
            /** Simulation Id */
            simulation_id: string | null;
            /**
             * Source Kind
             * @enum {string}
             */
            source_kind: "INCIDENT" | "CORRELATION" | "EVIDENCE_WINDOW";
            /**
             * Truncated
             * @constant
             */
            truncated: false;
        };
        /** ReplayEvent */
        ReplayEvent: {
            /**
             * Event Class
             * @enum {string}
             */
            event_class: "RAW_PROTOCOL" | "PROTOCOL_SEMANTIC" | "ASSET_CONTEXT" | "POLICY_FINDING" | "TELEMETRY" | "CORRELATION_FINDING" | "INCIDENT_EVENT";
            /**
             * Event Id
             * Format: uuid
             */
            event_id: string;
            evidence?: components["schemas"]["EvidenceRecordResponse"] | null;
            incident_event?: components["schemas"]["IncidentTimelineResponse"] | null;
            /**
             * Integrity Verified
             * @constant
             */
            integrity_verified: true;
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /**
             * Sort Rank
             * @enum {integer}
             */
            sort_rank: 10 | 20 | 30 | 40 | 50 | 60 | 70;
            /** Summary */
            summary: string;
        };
        /**
         * ResolutionStatus
         * @enum {string}
         */
        ResolutionStatus: "RESOLVED" | "UNKNOWN" | "CONFLICT";
        /** ResolvedRelationship */
        ResolvedRelationship: {
            relationship_type: components["schemas"]["RelationshipType"];
            /** Source Asset Key */
            source_asset_key: string;
            target_kind: components["schemas"]["RelationshipTargetKind"];
            /** Target Ref */
            target_ref: string;
        };
        /**
         * Role
         * @enum {string}
         */
        Role: "ADMIN" | "SOC_ANALYST" | "OT_ENGINEER" | "READ_ONLY";
        /** SemanticDerivationProvenance */
        SemanticDerivationProvenance: {
            /**
             * Canonicalization Version
             * @constant
             */
            canonicalization_version: "otsoc-canonical-json-1";
            /**
             * Decoder Name
             * @constant
             */
            decoder_name: "otsoc_offline_modbus_semantics";
            /**
             * Decoder Version
             * @constant
             */
            decoder_version: "1.0.0";
            /**
             * Derivation Kind
             * @constant
             */
            derivation_kind: "SEMANTIC_INTERPRETATION";
            /**
             * Educational Only
             * @constant
             */
            educational_only: true;
            /**
             * Profile Id
             * @constant
             */
            profile_id: "otsoc.synthetic_modbus.oil_gas_transfer";
            /** Profile Sha256 */
            profile_sha256: string;
            /**
             * Profile Version
             * @constant
             */
            profile_version: "1.0.0";
            /**
             * Source Evidence Id
             * Format: uuid
             */
            source_evidence_id: string;
            /** Source Evidence Integrity Sha256 */
            source_evidence_integrity_sha256: string;
        };
        /** SessionResponse */
        SessionResponse: {
            /**
             * Authenticated
             * @default true
             * @constant
             */
            authenticated: true;
            /** Csrf Token */
            csrf_token: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            user: components["schemas"]["UserResponse"];
        };
        /** SyntheticModbusEvent */
        SyntheticModbusEvent: {
            /** Address Offset */
            address_offset: number | null;
            capture_mode: components["schemas"]["CaptureMode"];
            /** Destination Identity */
            destination_identity: string;
            /**
             * Event Version
             * @constant
             */
            event_version: "1.0.0";
            /** Fixture Id */
            fixture_id: string;
            /** Function Code */
            function_code: number;
            message_role: components["schemas"]["MessageRole"];
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /** Protocol Id */
            protocol_id: number;
            /** Raw Value */
            raw_value: number | string | boolean | null;
            /** Source Identity */
            source_identity: string;
            /** Table Type */
            table_type: string | null;
            /** Transaction Id */
            transaction_id: number;
            /** Unit Id */
            unit_id: number;
        };
        /** SyntheticProtocolProvenance */
        SyntheticProtocolProvenance: {
            capture_mode: components["schemas"]["CaptureMode"];
            /**
             * Educational Only
             * @constant
             */
            educational_only: true;
            /**
             * Fixture Set Id
             * @constant
             */
            fixture_set_id: "otsoc.phase4b.synthetic_modbus";
            /**
             * Fixture Set Version
             * @constant
             */
            fixture_set_version: "1.0.0";
            /** Fixture Sha256 */
            fixture_sha256: string;
            /**
             * Generator
             * @constant
             */
            generator: "otsoc_static_fixture";
            /**
             * Generator Version
             * @constant
             */
            generator_version: "1.0.0";
        };
        /**
         * TimelineEntryType
         * @enum {string}
         */
        TimelineEntryType: "INCIDENT_CREATED" | "EVIDENCE_ADDED" | "STATUS_CHANGED" | "SEVERITY_CHANGED" | "ANALYST_NOTE_ADDED";
        /**
         * TrustClassification
         * @enum {string}
         */
        TrustClassification: "NO_OT_CONTROL_TRUST" | "LIMITED_CONTROL_TRUST" | "NON_NETWORK_PROCESS_CONTEXT" | "PASSIVE_OBSERVATION_ONLY" | "READ_ONLY_ANALYST_CONTEXT";
        /** UserCreateRequest */
        UserCreateRequest: {
            /** Display Name */
            display_name: string;
            /**
             * Password
             * Format: password
             */
            password: string;
            role: components["schemas"]["Role"];
            /** Username */
            username: string;
        };
        /** UserListResponse */
        UserListResponse: {
            /** Items */
            items: components["schemas"]["UserResponse"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /** UserMutationResponse */
        UserMutationResponse: {
            /**
             * Operation
             * @enum {string}
             */
            operation: "created" | "updated" | "password_reset";
            user: components["schemas"]["UserResponse"];
        };
        /** UserPatchRequest */
        UserPatchRequest: {
            /** Active */
            active?: boolean | null;
            /** Display Name */
            display_name?: string | null;
            /** Expected Version */
            expected_version: number;
            role?: components["schemas"]["Role"] | null;
        };
        /** UserResponse */
        UserResponse: {
            /** Active */
            active: boolean;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Display Name */
            display_name: string;
            /**
             * Password Changed At
             * Format: date-time
             */
            password_changed_at: string;
            role: components["schemas"]["Role"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /**
             * User Id
             * Format: uuid
             */
            user_id: string;
            /** Username */
            username: string;
            /** Version */
            version: number;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** ZoneDefinition */
        ZoneDefinition: {
            /** Allowed Relationship Types */
            allowed_relationship_types: components["schemas"]["RelationshipType"][];
            /** Name */
            name: string;
            /** Purpose */
            purpose: string;
            trust_classification: components["schemas"]["TrustClassification"];
            zone_id: components["schemas"]["ZoneId"];
        };
        /**
         * ZoneId
         * @enum {string}
         */
        ZoneId: "IT_ZONE" | "OT_CONTROL_ZONE" | "PROCESS_ZONE" | "MONITORING_ZONE" | "SOC_ZONE";
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    read_asset_catalog_api_v1_assets_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssetCatalogResponse"];
                };
            };
        };
    };
    read_asset_detail_api_v1_assets__asset_key__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                asset_key: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssetDetailResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionResponse"];
                };
            };
            /** @description Invalid local credentials. */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    read_session_api_v1_auth_session_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionResponse"];
                };
            };
        };
    };
    read_evidence_list_api_v1_evidence_get: {
        parameters: {
            query?: {
                scope?: "CURRENT" | "ALL_HISTORY" | "RUN";
                run_id?: string | null;
                limit?: number;
                offset?: number;
                cursor?: string | null;
                evidence_type?: ("simulator_telemetry" | "synthetic_protocol_event" | "protocol_semantic_event" | "asset_context_event" | "communication_policy_finding" | "correlation_finding") | null;
                source_key?: string | null;
                observed_from?: string | null;
                observed_to?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvidenceListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_evidence_api_v1_evidence_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EvidenceIngestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvidenceIngestionReceipt"];
                };
            };
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvidenceIngestionReceipt"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_evidence_api_v1_evidence__evidence_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                evidence_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvidenceRecordResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_incident_assignees_api_v1_incident_assignees_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignableUserListResponse"];
                };
            };
        };
    };
    read_incident_list_api_v1_incidents_get: {
        parameters: {
            query?: {
                scope?: "CURRENT" | "ALL_HISTORY" | "RUN";
                run_id?: string | null;
                status?: string | null;
                category?: string | null;
                severity?: string | null;
                asset_id?: string | null;
                observed_from?: string | null;
                observed_to?: string | null;
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_incident_detail_api_v1_incidents__incident_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentDetailResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_incident_assignment_api_v1_incidents__incident_id__assignment_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncidentAssignmentPatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentMutationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_incident_audit_api_v1_incidents__incident_id__audit_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentAuditListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_incident_disposition_api_v1_incidents__incident_id__disposition_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncidentDispositionPatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentMutationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_incident_note_api_v1_incidents__incident_id__notes_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncidentNoteCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentMutationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_incident_report_api_v1_incidents__incident_id__report_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentReportResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_incident_report_api_v1_incidents__incident_id__report_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncidentReportPutRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentReportResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_incident_status_api_v1_incidents__incident_id__status_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncidentStatusPatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentMutationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    post_lab_baseline_api_v1_lab_baseline_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["LabNoFieldsRequest"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LabContextResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_lab_catalog_api_v1_lab_catalog_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LabCatalogResponse"];
                };
            };
        };
    };
    get_lab_context_api_v1_lab_context_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LabContextResponse"];
                };
            };
        };
    };
    post_lab_reset_api_v1_lab_reset_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["LabNoFieldsRequest"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LabContextResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_lab_runs_api_v1_lab_runs_get: {
        parameters: {
            query?: {
                scenario_id?: components["schemas"]["LabScenarioId"] | null;
                status?: components["schemas"]["LabRunState"] | null;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LabRunListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_lab_run_api_v1_lab_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LabRunResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    post_lab_start_api_v1_lab_start_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LabRunStartRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LabStartResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    metadata_api_v1_meta_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MetadataResponse"];
                };
            };
        };
    };
    read_overview_summary_api_v1_overview_summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OverviewSummaryResponse"];
                };
            };
        };
    };
    read_replay_bundle_api_v1_replay_get: {
        parameters: {
            query?: {
                incident_id?: string | null;
                run_id?: string | null;
                correlation_evidence_id?: string | null;
                simulation_id?: string | null;
                configuration_hash?: string | null;
                observed_from?: string | null;
                observed_to?: string | null;
                evidence_type?: string[] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReplayBundleResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_users_api_v1_users_get: {
        parameters: {
            query?: {
                role?: components["schemas"]["Role"] | null;
                active?: boolean | null;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_user_api_v1_users_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserMutationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_user_api_v1_users__user_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserPatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserMutationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reset_user_password_api_v1_users__user_id__password_reset_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordResetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserMutationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    liveness_health_live_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LivenessResponse"];
                };
            };
        };
    };
    readiness_health_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadinessResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadinessResponse"];
                };
            };
        };
    };
}
