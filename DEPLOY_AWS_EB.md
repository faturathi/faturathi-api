# Deploy the Faturathi Django backend to AWS Elastic Beanstalk

## AWS resources

Create these before the first deployment:

1. An RDS PostgreSQL database in the same VPC as Elastic Beanstalk. Permit TCP 5432 from the
   Elastic Beanstalk instance security group, not from the public internet.
2. A private S3 bucket for Django static and media assets.
3. A CloudFront distribution whose S3 origin uses Origin Access Control (OAC). Use its hostname
   as `AWS_CLOUDFRONT_DOMAIN`.
4. An Elastic Beanstalk EC2 instance profile with access to the application's S3 prefixes.
5. An IAM user or deployment role allowed to upload Beanstalk application versions and update
   the target environment.

For the initial setup, the deployment identity can use AWS's
`AdministratorAccess-AWSElasticBeanstalk` managed policy plus S3 access to the regional
`elasticbeanstalk-<region>-<account-id>` deployment bucket. Restrict both policies to the specific
application, environment, and bucket after the first successful rollout.

## First environment creation

Run these commands from the backend repository root:

```powershell
python -m pip install --upgrade awsebcli
aws configure
eb init -p python-3.13 --region <AWS_REGION> <APPLICATION_NAME>
eb create <ENVIRONMENT_NAME>
```

The RDS instance is intentionally created independently. Do not attach an EB-managed database;
terminating an environment must not delete production invoice data.

Set environment properties in the Elastic Beanstalk console or with `eb setenv`:

```powershell
eb setenv DEBUG=False SECRET_KEY=<strong-random-secret> `
  ALLOWED_HOSTS=<environment>.elasticbeanstalk.com,api.example.com `
  CSRF_TRUSTED_ORIGINS=https://api.example.com,https://app.example.com `
  CORS_ALLOW_ALL=False CORS_ALLOWED_ORIGINS=https://app.example.com `
  DB_NAME=<database> DB_USER=<user> DB_PASSWORD=<password> `
  DB_HOST=<rds-endpoint> DB_PORT=5432 `
  AWS_STORAGE_BUCKET_NAME=<bucket> AWS_S3_REGION_NAME=<region> `
  AWS_CLOUDFRONT_DOMAIN=<distribution>.cloudfront.net
```

Prefer AWS Secrets Manager or SSM Parameter Store for production database credentials. The values
must ultimately be available to the Django process as environment variables.

The first deployment is created by `eb create`. Later manual deployments use `eb deploy`.

## GitHub configuration

In the backend GitHub repository, create a `production` Environment and add:

Repository secrets:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Repository variables:

- `AWS_REGION`
- `EB_APPLICATION_NAME`
- `EB_ENVIRONMENT_NAME`

Every push to `main` runs Django checks and tests, then packages the repository and deploys a new
Elastic Beanstalk application version. The workflow can also be started manually.

For stronger security, replace the long-lived access-key inputs with GitHub OIDC and an AWS IAM
role after the first deployment is working.

## Static and media files

`collectstatic` runs once per deployment through `.ebextensions/django.config`. When
`AWS_STORAGE_BUCKET_NAME` is set, Django uploads static assets directly to the `static/` prefix in
S3. Browser URLs use CloudFront when `AWS_CLOUDFRONT_DOMAIN` is configured. Gunicorn does not serve
static or uploaded files.

The Elastic Beanstalk instance profile needs at least `s3:ListBucket`, `s3:GetObject`,
`s3:PutObject`, and `s3:DeleteObject` for the selected bucket/prefixes.

## Health and verification

Elastic Beanstalk checks `GET /api/health`, which does not require authentication. After deployment:

```powershell
eb status
eb health
eb logs
curl https://<environment-domain>/api/health
```
