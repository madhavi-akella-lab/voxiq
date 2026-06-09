"""
VoxIQ — AWS CDK Infrastructure Stack
Creates every AWS resource the project needs with a single `cdk deploy`.
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
    aws_apigateway as apigw,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
    aws_ssm as ssm,
)
from constructs import Construct


class VoxIQStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        account = self.account

        # ------------------------------------------------------------------ #
        # S3 — Raw audio bucket + Frontend hosting bucket
        # ------------------------------------------------------------------ #
        audio_bucket = s3.Bucket(
            self, "RawAudioBucket",
            bucket_name=f"voxiq-raw-audio-{account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            cors=[s3.CorsRule(
                allowed_methods=[s3.HttpMethods.PUT],
                allowed_origins=["*"],
                allowed_headers=["*"],
                max_age=3000,
            )],
        )

        results_bucket = s3.Bucket(
            self, "ResultsBucket",
            bucket_name=f"voxiq-results-{account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        frontend_bucket = s3.Bucket(
            self, "FrontendBucket",
            bucket_name=f"voxiq-frontend-{account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            website_index_document="index.html",
            website_error_document="index.html",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False,
            ),
        )

        # ------------------------------------------------------------------ #
        # DynamoDB — Call records table
        # ------------------------------------------------------------------ #
        table = dynamodb.Table(
            self, "CallRecordsTable",
            table_name="VoxIQ-CallRecords",
            partition_key=dynamodb.Attribute(name="call_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="created_at", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
        )

        # GSI-1: list calls by org + date
        table.add_global_secondary_index(
            index_name="OrgDateIndex",
            partition_key=dynamodb.Attribute(name="org_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="created_at", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # GSI-2: find calls by status
        table.add_global_secondary_index(
            index_name="StatusIndex",
            partition_key=dynamodb.Attribute(name="status", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="created_at", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.INCLUDE,
            non_key_attributes=["call_id", "org_id", "caller_phone", "duration_seconds", "routing_category"],
        )

        # GSI-3: caller history by phone number
        table.add_global_secondary_index(
            index_name="PhoneIndex",
            partition_key=dynamodb.Attribute(name="caller_phone", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="created_at", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.INCLUDE,
            non_key_attributes=["call_id", "org_id", "status", "summary", "sentiment", "routing_category", "duration_seconds"],
        )

        # ------------------------------------------------------------------ #
        # Shared Lambda environment + IAM
        # ------------------------------------------------------------------ #
        shared_env = {
            "DYNAMODB_TABLE":  table.table_name,
            "AUDIO_BUCKET":    audio_bucket.bucket_name,
            "RESULTS_BUCKET":  results_bucket.bucket_name,
        }

        lambda_role = iam.Role(
            self, "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )
        table.grant_read_write_data(lambda_role)
        audio_bucket.grant_read_write(lambda_role)
        results_bucket.grant_read_write(lambda_role)
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["transcribe:StartTranscriptionJob", "transcribe:GetTranscriptionJob"],
            resources=["*"],
        ))
        # AWS Comprehend — free tier, no API key needed
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "comprehend:DetectSentiment",
                "comprehend:DetectKeyPhrases",
                "comprehend:DetectEntities",
            ],
            resources=["*"],
        ))

        # ------------------------------------------------------------------ #
        # Lambda 1 — Presign URL (returns a secure upload URL to the browser)
        # ------------------------------------------------------------------ #
        presign_fn = lambda_.Function(
            self, "PresignUrlFn",
            function_name="voxiq-presign-url",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../backend/lambdas/presign_url"),
            role=lambda_role,
            environment=shared_env,
            timeout=Duration.seconds(10),
        )

        # ------------------------------------------------------------------ #
        # Lambda 2 — S3 trigger (fires when audio lands, starts Transcribe)
        # ------------------------------------------------------------------ #
        s3_trigger_fn = lambda_.Function(
            self, "S3TriggerFn",
            function_name="voxiq-s3-trigger",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../backend/lambdas/s3_trigger"),
            role=lambda_role,
            environment=shared_env,
            timeout=Duration.seconds(30),
        )
        audio_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(s3_trigger_fn),
            s3.NotificationKeyFilter(prefix="raw-audio/"),
        )

        # ------------------------------------------------------------------ #
        # Lambda 3 — Claude analysis (polls for Transcribe completion, calls Claude)
        # ------------------------------------------------------------------ #
        claude_fn = lambda_.Function(
            self, "ClaudeAnalysisFn",
            function_name="voxiq-claude-analysis",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../backend/lambdas/claude_analysis"),
            role=lambda_role,
            environment=shared_env,
            timeout=Duration.seconds(60),
            memory_size=256,
        )
        results_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(claude_fn),
            s3.NotificationKeyFilter(prefix="transcripts/"),
        )

        # ------------------------------------------------------------------ #
        # Lambda 4 — Get calls (API endpoint for the dashboard)
        # ------------------------------------------------------------------ #
        get_calls_fn = lambda_.Function(
            self, "GetCallsFn",
            function_name="voxiq-get-calls",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../backend/lambdas/get_calls"),
            role=lambda_role,
            environment=shared_env,
            timeout=Duration.seconds(15),
        )

        # ------------------------------------------------------------------ #
        # API Gateway — REST API
        # ------------------------------------------------------------------ #
        api = apigw.RestApi(
            self, "VoxIQApi",
            rest_api_name="voxiq-api",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        calls_resource = api.root.add_resource("calls")
        calls_resource.add_method("GET", apigw.LambdaIntegration(get_calls_fn))

        upload_resource = api.root.add_resource("upload-url")
        upload_resource.add_method("GET", apigw.LambdaIntegration(presign_fn))

        # ------------------------------------------------------------------ #
        # CloudFront — serves the React frontend
        # ------------------------------------------------------------------ #
        distribution = cloudfront.Distribution(
            self, "FrontendDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3StaticWebsiteOrigin(frontend_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                )
            ],
        )

        # ------------------------------------------------------------------ #
        # Outputs — printed after `cdk deploy`
        # ------------------------------------------------------------------ #
        CfnOutput(self, "ApiUrl",       value=api.url,                         description="API Gateway URL — paste into frontend .env as VITE_API_URL")
        CfnOutput(self, "DashboardUrl", value=f"https://{distribution.domain_name}", description="Your React dashboard URL")
        CfnOutput(self, "AudioBucketName",  value=audio_bucket.bucket_name,        description="S3 bucket for raw audio uploads")
        CfnOutput(self, "FrontendBucketName", value=frontend_bucket.bucket_name,   description="S3 bucket — sync your React build here")
